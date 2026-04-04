"""Unit tests for AppointmentService.

Tests generate_narrative(), generate_scenarios(), and generate_pdf() in isolation
— all dependencies are mocked so no DB or LLM calls are made.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import DatabaseError, EntityNotFoundError
from app.utils.sanitize import sanitize_urgent_symptom
from app.models.appointment import (
    AppointmentContext,
    AppointmentGoal,
    AppointmentPrepGenerateResponse,
    AppointmentPrepNarrativeResponse,
    AppointmentPrepScenariosResponse,
    AppointmentType,
    CheatsheetResponse,
    Concern,
    DismissalExperience,
    ProviderSummaryResponse,
    QuestionGroup,
)
from app.services.appointment import AppointmentService


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context():
    return AppointmentContext(
        appointment_type=AppointmentType.established_relationship,
        goal=AppointmentGoal.explore_hrt,
        dismissed_before=DismissalExperience.once_or_twice,
        urgent_symptom=None,
    )


@pytest.fixture
def mock_appointment_repo(context):
    mock = AsyncMock()
    mock.get_context.return_value = context
    mock.save_narrative.return_value = None
    mock.save_frequency_stats.return_value = None
    mock.save_scenarios.return_value = None
    mock.get_symptom_reference.return_value = {
        "sym-1": {"name": "Hot flashes", "category": "vasomotor"},
        "sym-2": {"name": "Night sweats", "category": "vasomotor"},
    }
    mock.get_concerns.return_value = [
        Concern(text="Discuss HRT options"),
        Concern(text="Ask about dosage"),
    ]
    mock.get_appointment_data.return_value = {
        "narrative": "Logs show frequent hot flashes and night sweats.",
        "concerns": [{"text": "Discuss HRT options", "comment": None}],
        "scenarios": [{"id": "scenario-1", "title": "HRT risk", "suggestion": "..."}],
        "frequency_stats": [],
        "cooccurrence_stats": [],
    }
    mock.save_pdf_metadata.return_value = None
    return mock


@pytest.fixture
def mock_symptoms_repo():
    mock = AsyncMock()

    # Create fake log objects with .symptoms attribute
    fake_symptom = MagicMock()
    fake_symptom.id = "sym-1"

    fake_log = MagicMock()
    fake_log.symptoms = [fake_symptom]

    mock.get_logs.return_value = ([fake_log], 1)
    return mock


@pytest.fixture
def mock_user_repo():
    mock = AsyncMock()
    mock.get_context.return_value = ("perimenopause", 48)
    return mock


@pytest.fixture
def mock_llm_service():
    svc = MagicMock()
    svc.generate_narrative = AsyncMock(return_value="Generated narrative text.")
    svc.generate_scenario_suggestions = AsyncMock(
        return_value='[{"suggestion": "You can advocate for treatment by citing NAMS guidelines.", "sources": []}]'
    )
    svc.generate_provider_summary_content = AsyncMock(
        return_value=ProviderSummaryResponse(
            opening="Patient presents for discussion.",
            key_patterns="Hot flashes co-occur with night sweats.",
            closing="Patient seeks treatment options.",
        )
    )
    svc.generate_cheatsheet_content = AsyncMock(
        return_value=CheatsheetResponse(
            opening_statement="I am 48 and experiencing hot flashes.",
            question_groups=[
                QuestionGroup(
                    topic="Hot flashes", questions=["Could you help me understand..."]
                )
            ],
        )
    )
    return svc


@pytest.fixture
def mock_storage_service():
    mock = AsyncMock()
    mock.upload_pdf.return_value = "https://storage.example.com/provider-summary.pdf"
    return mock


@pytest.fixture
def mock_pdf_service():
    mock = MagicMock()
    mock.build_provider_summary_pdf.return_value = b"%PDF-provider"
    mock.build_cheatsheet_pdf.return_value = b"%PDF-cheatsheet"
    return mock


@pytest.fixture
def mock_rag_retriever():
    retriever = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def service(
    mock_appointment_repo,
    mock_symptoms_repo,
    mock_user_repo,
    mock_llm_service,
    mock_storage_service,
    mock_pdf_service,
    mock_rag_retriever,
):
    return AppointmentService(
        appointment_repo=mock_appointment_repo,
        symptoms_repo=mock_symptoms_repo,
        user_repo=mock_user_repo,
        llm_service=mock_llm_service,
        storage_service=mock_storage_service,
        pdf_service=mock_pdf_service,
        rag_retriever=mock_rag_retriever,
    )


# ---------------------------------------------------------------------------
# generate_narrative
# ---------------------------------------------------------------------------


class TestGenerateNarrative:
    @pytest.mark.asyncio
    async def test_returns_narrative_response(self, service):
        result = await service.generate_narrative("appt-123", "user-456", days_back=60)

        assert isinstance(result, AppointmentPrepNarrativeResponse)
        assert result.appointment_id == "appt-123"
        assert result.next_step == "prioritize"
        assert len(result.narrative) > 0

    @pytest.mark.asyncio
    async def test_calls_llm_with_prompts(self, service, mock_llm_service):
        # CATCHES: appointment.py calling provider directly instead of going through
        # llm_service.generate_narrative — would bypass the service abstraction layer
        await service.generate_narrative("appt-123", "user-456", days_back=60)

        mock_llm_service.generate_narrative.assert_called_once()
        call_kwargs = mock_llm_service.generate_narrative.call_args[1]
        assert "logs show" in call_kwargs["system_prompt"].lower()
        assert "system_prompt" in call_kwargs
        assert "user_prompt" in call_kwargs

    @pytest.mark.asyncio
    async def test_saves_narrative_to_repo(self, service, mock_appointment_repo):
        await service.generate_narrative("appt-123", "user-456", days_back=60)

        mock_appointment_repo.save_narrative.assert_called_once_with(
            "appt-123", "user-456", "Generated narrative text."
        )

    @pytest.mark.asyncio
    async def test_returns_empty_narrative_when_no_logs(
        self, service, mock_symptoms_repo
    ):
        mock_symptoms_repo.get_logs.return_value = ([], 0)

        result = await service.generate_narrative("appt-123", "user-456", days_back=60)

        assert "No symptom logs found" in result.narrative
        assert result.next_step == "prioritize"

    @pytest.mark.asyncio
    async def test_raises_entity_not_found_when_appointment_missing(
        self, service, mock_appointment_repo
    ):
        mock_appointment_repo.get_context.side_effect = EntityNotFoundError(
            "Appointment not found"
        )

        with pytest.raises(EntityNotFoundError):
            await service.generate_narrative("bad-id", "user-456", days_back=60)

    @pytest.mark.asyncio
    async def test_raises_database_error_when_user_context_fails(
        self, service, mock_user_repo
    ):
        mock_user_repo.get_context.side_effect = Exception("DB failure")

        with pytest.raises(DatabaseError):
            await service.generate_narrative("appt-123", "user-456", days_back=60)

    @pytest.mark.asyncio
    async def test_raises_database_error_when_logs_fail(
        self, service, mock_symptoms_repo
    ):
        mock_symptoms_repo.get_logs.side_effect = Exception("Query timeout")

        with pytest.raises(DatabaseError):
            await service.generate_narrative("appt-123", "user-456", days_back=60)

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_times_out(
        self, service, mock_llm_service
    ):
        # CATCHES: error handling missing after switching from provider.chat_completion
        # to llm_service.generate_narrative — TimeoutError would propagate uncaught
        mock_llm_service.generate_narrative.side_effect = TimeoutError()

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_narrative("appt-123", "user-456", days_back=60)

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_fails(
        self, service, mock_llm_service
    ):
        # CATCHES: generic exceptions from generate_narrative not converted to
        # DatabaseError — would surface as 500 with internal LLM error details
        mock_llm_service.generate_narrative.side_effect = Exception("API error")

        with pytest.raises(DatabaseError):
            await service.generate_narrative("appt-123", "user-456", days_back=60)


# ---------------------------------------------------------------------------
# generate_scenarios
# ---------------------------------------------------------------------------


class TestGenerateScenarios:
    @pytest.mark.asyncio
    async def test_returns_scenarios_response(self, service):
        result = await service.generate_scenarios("appt-123", "user-456")

        assert isinstance(result, AppointmentPrepScenariosResponse)
        assert result.appointment_id == "appt-123"
        assert result.next_step == "generate"
        assert len(result.scenarios) > 0

    @pytest.mark.asyncio
    async def test_scenarios_have_required_fields(self, service):
        result = await service.generate_scenarios("appt-123", "user-456")

        for scenario in result.scenarios:
            assert scenario.id
            assert scenario.title
            assert scenario.situation
            assert scenario.suggestion
            assert scenario.category

    @pytest.mark.asyncio
    async def test_saves_scenarios_to_repo(self, service, mock_appointment_repo):
        await service.generate_scenarios("appt-123", "user-456")

        mock_appointment_repo.save_scenarios.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_entity_not_found_when_appointment_missing(
        self, service, mock_appointment_repo
    ):
        mock_appointment_repo.get_context.side_effect = EntityNotFoundError(
            "Appointment not found"
        )

        with pytest.raises(EntityNotFoundError):
            await service.generate_scenarios("bad-id", "user-456")

    @pytest.mark.asyncio
    async def test_uses_empty_concerns_when_fetch_fails(
        self, service, mock_appointment_repo, mock_llm_service
    ):
        """Concerns fetch failure should not abort scenarios — use empty list."""
        mock_appointment_repo.get_concerns.side_effect = Exception("Step 3 not done")

        result = await service.generate_scenarios("appt-123", "user-456")

        assert isinstance(result, AppointmentPrepScenariosResponse)
        # LLM was called with concerns=[] instead of failing
        call_kwargs = mock_llm_service.generate_scenario_suggestions.call_args[1]
        assert call_kwargs["concerns"] == []

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_times_out(
        self, service, mock_llm_service
    ):
        mock_llm_service.generate_scenario_suggestions.side_effect = TimeoutError()

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_scenarios("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_json_parsing_fails(
        self, service, mock_llm_service
    ):
        mock_llm_service.generate_scenario_suggestions.return_value = "not valid json {"

        with pytest.raises(DatabaseError, match="Failed to parse"):
            await service.generate_scenarios("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_rag_retriever_called_for_each_scenario(
        self, service, mock_rag_retriever
    ):
        # CATCHES: rag_retriever not wired into generate_scenarios — scenario
        # suggestions would be generated without any RAG grounding, sources empty
        await service.generate_scenarios("appt-123", "user-456")

        # rag_retriever should be called at least once (once per selected scenario)
        assert mock_rag_retriever.call_count >= 1

    @pytest.mark.asyncio
    async def test_rag_chunks_passed_to_llm_service(
        self, service, mock_rag_retriever, mock_llm_service
    ):
        # CATCHES: rag_chunks collected but not forwarded to LLM — prompt builder
        # never sees the source documents and scenario suggestions remain ungrounded
        mock_rag_retriever.return_value = [
            {
                "title": "NAMS 2022",
                "content": "MHT is effective for vasomotor symptoms.",
            }
        ]

        await service.generate_scenarios("appt-123", "user-456")

        call_kwargs = mock_llm_service.generate_scenario_suggestions.call_args[1]
        assert "rag_chunks" in call_kwargs
        assert (
            call_kwargs["rag_chunks"] is not None and len(call_kwargs["rag_chunks"]) > 0
        )

    @pytest.mark.asyncio
    async def test_scenarios_generated_without_rag_when_retriever_returns_empty(
        self, service, mock_rag_retriever, mock_llm_service
    ):
        # CATCHES: empty RAG result causes crash — fallback must work cleanly
        # when no relevant chunks are found (no-source generation is valid)
        mock_rag_retriever.return_value = []

        result = await service.generate_scenarios("appt-123", "user-456")

        assert isinstance(result, AppointmentPrepScenariosResponse)
        call_kwargs = mock_llm_service.generate_scenario_suggestions.call_args[1]
        # Empty chunks still passed (not None) — prompt builder handles it
        assert "rag_chunks" in call_kwargs

    @pytest.mark.asyncio
    async def test_duplicate_rag_chunks_deduplicated_before_llm_call(
        self, service, mock_rag_retriever, mock_llm_service
    ):
        # CATCHES: same chunk returned for multiple scenarios passed to LLM
        # multiple times — inflates prompt size and wastes tokens
        duplicate_chunk = {
            "id": "chunk-1",
            "title": "NAMS 2022",
            "content": "MHT is effective.",
        }
        mock_rag_retriever.return_value = [duplicate_chunk]

        await service.generate_scenarios("appt-123", "user-456")

        call_kwargs = mock_llm_service.generate_scenario_suggestions.call_args[1]
        rag_chunks = call_kwargs["rag_chunks"]
        # Even though each scenario retrieval returns the same chunk, only one copy
        # should reach the LLM
        chunk_ids = [c.get("id") for c in rag_chunks]
        assert chunk_ids.count("chunk-1") == 1


# ---------------------------------------------------------------------------
# generate_pdf
# ---------------------------------------------------------------------------


class TestGeneratePdf:
    @pytest.mark.asyncio
    async def test_returns_generate_response(self, service):
        result = await service.generate_pdf("appt-123", "user-456")

        assert isinstance(result, AppointmentPrepGenerateResponse)
        assert result.appointment_id == "appt-123"
        assert "https://" in result.provider_summary_url
        assert "https://" in result.personal_cheat_sheet_url

    @pytest.mark.asyncio
    async def test_uploads_two_pdfs(self, service, mock_storage_service):
        await service.generate_pdf("appt-123", "user-456")

        assert mock_storage_service.upload_pdf.call_count == 2

    @pytest.mark.asyncio
    async def test_generates_two_llm_documents(self, service, mock_llm_service):
        # CATCHES: generate_pdf using old generate_pdf_content instead of the two
        # new structured methods — would produce markdown PDFs not structured ones
        await service.generate_pdf("appt-123", "user-456")

        mock_llm_service.generate_provider_summary_content.assert_called_once()
        mock_llm_service.generate_cheatsheet_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_saves_pdf_metadata(self, service, mock_appointment_repo):
        await service.generate_pdf("appt-123", "user-456")

        mock_appointment_repo.save_pdf_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_entity_not_found_when_appointment_missing(
        self, service, mock_appointment_repo
    ):
        mock_appointment_repo.get_context.side_effect = EntityNotFoundError(
            "Appointment not found"
        )

        with pytest.raises(EntityNotFoundError):
            await service.generate_pdf("bad-id", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_appointment_data_missing(
        self, service, mock_appointment_repo
    ):
        mock_appointment_repo.get_appointment_data.side_effect = EntityNotFoundError(
            "No data"
        )

        with pytest.raises(EntityNotFoundError):
            await service.generate_pdf("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_times_out(
        self, service, mock_llm_service
    ):
        # CATCHES: TimeoutError from generate_provider_summary_content not converted
        # to DatabaseError — would surface as unhandled 500
        mock_llm_service.generate_provider_summary_content.side_effect = TimeoutError()

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_pdf("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_upload_fails(
        self, service, mock_storage_service
    ):
        mock_storage_service.upload_pdf.side_effect = Exception("S3 unavailable")

        with pytest.raises(DatabaseError, match="upload"):
            await service.generate_pdf("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_cheatsheet_times_out(
        self, service, mock_llm_service
    ):
        """Test that timeout on cheatsheet_content is caught and converted to DatabaseError."""
        # CATCHES: cheatsheet task timeout in asyncio.gather() not caught —
        # would surface as unhandled 500 or TimeoutError
        mock_llm_service.generate_cheatsheet_content.side_effect = TimeoutError(
            "LLM request timed out"
        )

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_pdf("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_cheatsheet_fails(
        self, service, mock_llm_service
    ):
        """Test that non-timeout exception on cheatsheet_content is caught."""
        # CATCHES: cheatsheet task exception in asyncio.gather() not caught —
        # would surface as unhandled 500 with LLM error details
        mock_llm_service.generate_cheatsheet_content.side_effect = ValueError(
            "Invalid cheatsheet response"
        )

        with pytest.raises(DatabaseError, match="Failed to generate"):
            await service.generate_pdf("appt-123", "user-456")


# ---------------------------------------------------------------------------
# _select_scenarios (private helper)
# ---------------------------------------------------------------------------


class TestSelectScenarios:
    """Tests for _select_scenarios() after JSON-config refactor.

    _select_scenarios() returns list[dict] where each dict has "title" (str)
    and "category" (str). _get_scenario_category() has been deleted — category
    comes directly from the JSON config.
    """

    def _make_service(self):
        """Create service instance without initializing deps, but load scenario config."""
        svc = AppointmentService.__new__(AppointmentService)
        svc._scenario_config = svc._load_scenario_config()
        return svc

    def _context(self, goal, dismissed=DismissalExperience.once_or_twice, urgent=None):
        return AppointmentContext(
            appointment_type=AppointmentType.established_relationship,
            goal=goal,
            dismissed_before=dismissed,
            urgent_symptom=urgent,
        )

    def _titles(self, scenarios: list) -> list[str]:
        """Extract title strings from scenario dicts."""
        return [s["title"] for s in scenarios]

    # ── Return type contract ─────────────────────────────────────────────────

    def test_returns_list_of_dicts(self):
        # CATCHES: still returning list[str] after refactor — callers that
        # unpack s["title"] and s["category"] would crash with TypeError
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        assert isinstance(scenarios, list)
        assert all(isinstance(s, dict) for s in scenarios)

    def test_each_dict_has_title_and_category(self):
        # CATCHES: missing "category" key — generate_scenarios() reads
        # s["category"] to build ScenarioCard and would raise KeyError
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        for s in scenarios:
            assert "title" in s, f"Missing 'title' key in {s}"
            assert "category" in s, f"Missing 'category' key in {s}"
            assert isinstance(s["title"], str)
            assert isinstance(s["category"], str)

    def test_result_has_at_most_7_scenarios(self):
        # CATCHES: removing the [:7] cap — generate_scenarios() zips the
        # scenario list with LLM suggestions and must stay within token budget
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="brain fog")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        assert len(scenarios) <= 7

    def test_cap_at_7_when_many_unique_scenarios(self):
        # CATCHES: comment says "cap at 7" but no [:7] slice exists — deduplicated
        # list with 10+ entries would be returned in full, exceeding token budget
        svc = self._make_service()
        # Inject a bloated config with 10+ unique scenarios for a goal
        import copy

        original_config = svc._scenario_config
        bloated_config = copy.deepcopy(original_config)
        bloated_config["goal_scenarios"]["assess_status"] = [
            {"title": f"Unique scenario title {i}", "category": "general"}
            for i in range(12)
        ]
        svc._scenario_config = bloated_config
        ctx = self._context(AppointmentGoal.assess_status)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        assert len(scenarios) <= 7

    def test_result_is_deduplicated_by_title(self):
        # CATCHES: dedup using set() on dicts (unhashable) or not deduplicating
        # at all — explore_hrt + universal both contain "will go away" strings
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert len(titles) == len(set(titles))

    # ── Goal-based routing ───────────────────────────────────────────────────

    def test_explore_hrt_includes_hrt_safety_scenario(self):
        # CATCHES: wrong goal key lookup — explore_hrt maps to wrong group
        # and returns unrelated scenarios
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "breast cancer" in t.lower() or "hormone therapy increases" in t.lower()
            for t in titles
        )

    def test_explore_hrt_scenario_has_hrt_safety_category(self):
        # CATCHES: assigning wrong category to HRT risk scenario — frontend
        # groups scenarios by category for display
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        hrt_risk = next(
            (s for s in scenarios if "breast cancer" in s["title"].lower()), None
        )
        assert hrt_risk is not None
        assert hrt_risk["category"] == "hrt-safety"

    def test_optimize_current_treatment_includes_severity_dismissal(self):
        # CATCHES: optimize_current_treatment mapping to wrong group —
        # "aren't severe enough" scenario is specific to this goal
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.optimize_current_treatment)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("severe" in t.lower() or "lifestyle" in t.lower() for t in titles)

    def test_assess_status_includes_wait_and_see_scenario(self):
        # CATCHES: assess_status falling through to empty — goal value typo
        # or missing key in JSON would return zero scenarios
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.assess_status)
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("go away" in t.lower() or "stressed" in t.lower() for t in titles)

    # ── Urgent-symptom keyword routing ───────────────────────────────────────

    def test_urgent_cognitive_selects_cognitive_scenarios(self):
        # CATCHES: keyword "brain fog" not matching cognitive group — user
        # selecting brain fog as urgent symptom gets generic scenarios
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="brain fog")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("brain fog" in t.lower() or "cognitive" in t.lower() for t in titles)

    def test_urgent_hot_flash_selects_vasomotor_scenarios(self):
        # CATCHES: vasomotor keyword not matched — hot flash scenarios missing
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="hot flashes")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "hot flash" in t.lower()
            or "layer" in t.lower()
            or "antidepressant" in t.lower()
            for t in titles
        )

    def test_urgent_sleep_selects_sleep_scenarios(self):
        # CATCHES: sleep keyword missing from config — insomnia scenarios silently
        # fall through to generic fallback
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="insomnia")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("sleep" in t.lower() or "melatonin" in t.lower() for t in titles)

    def test_urgent_anxiety_selects_anxiety_scenarios(self):
        # CATCHES: anxiety keyword match broken — gets generic dismissals
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="anxiety")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "meditation" in t.lower() or "psychiatrist" in t.lower() for t in titles
        )

    def test_urgent_vaginal_selects_vaginal_scenarios(self):
        # CATCHES: vaginal keyword group missing or wrong — patient with vaginal
        # dryness gets unrelated scenarios
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="vaginal dryness")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("lube" in t.lower() or "vaginal" in t.lower() for t in titles)

    def test_urgent_joint_pain_selects_joint_scenarios(self):
        # CATCHES: "pain" keyword not in joint group — user with joint pain
        # falls through to generic fallback silently
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="joint pain")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "rheumatologist" in t.lower() or "arthritis" in t.lower() for t in titles
        )

    def test_urgent_bladder_selects_bladder_scenarios(self):
        # CATCHES: bladder group missing from JSON entirely — this was the
        # primary gap in the original PRD spec
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="bladder leakage")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "kegel" in t.lower() or "pelvic" in t.lower() or "bladder" in t.lower()
            for t in titles
        )

    def test_urgent_urinary_keyword_also_matches_bladder_group(self):
        # CATCHES: only "bladder" keyword in group — "urinary" issues miss the
        # group and get generic fallback
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.urgent_symptom, urgent="urinary incontinence"
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "kegel" in t.lower() or "pelvic" in t.lower() or "bladder" in t.lower()
            for t in titles
        )

    def test_urgent_mood_selects_mood_scenarios(self):
        # CATCHES: "depression" keyword not matched — mood/depression scenarios
        # fallthrough to generic
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.urgent_symptom, urgent="depression and mood changes"
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "antidepressant" in t.lower() or "psychological" in t.lower()
            for t in titles
        )

    def test_urgent_fatigue_selects_fatigue_scenarios(self):
        # CATCHES: "tired" keyword not in fatigue group — user reporting
        # tiredness gets wrong scenarios
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.urgent_symptom, urgent="feeling tired all the time"
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any(
            "fatigue" in t.lower() or "thyroid" in t.lower() or "exercise" in t.lower()
            for t in titles
        )

    def test_urgent_skin_hair_selects_skin_scenarios(self):
        # CATCHES: "hair" keyword missing — hair loss symptom falls through
        # to generic fallback
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="hair loss")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("dermatologist" in t.lower() or "hair" in t.lower() for t in titles)

    def test_unknown_keyword_uses_fallback_scenarios(self):
        # CATCHES: no fallback group in JSON — unknown symptom returns empty
        # list which causes generate_scenarios() to produce 0 cards
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.urgent_symptom, urgent="completely unknown symptom xyz"
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        assert len(scenarios) > 0

    def test_urgent_path_appends_universal_scenarios(self):
        # CATCHES: universal scenarios not appended in urgent path — "will go
        # away on their own" scenario always applies but would be missing
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="brain fog")
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert any("go away" in t.lower() or "stressed" in t.lower() for t in titles)

    def test_dismissed_before_does_not_affect_scenarios(self):
        # CATCHES: dismissed_before logic still present after refactor —
        # "What are the triggers?" is not a dismissal scenario and was removed
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.explore_hrt,
            dismissed=DismissalExperience.multiple_times,
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        titles = self._titles(scenarios)
        assert not any("triggers" in t.lower() for t in titles)

    # ── Urgent symptom input sanitization ────────────────────────────────────

    def test_sanitize_urgent_symptom_returns_none_for_empty_input(self):
        # CATCHES: None or empty string not handled — would cause downstream errors
        assert sanitize_urgent_symptom(None) is None
        assert sanitize_urgent_symptom("") is None
        assert sanitize_urgent_symptom("   ") is None

    def test_sanitize_urgent_symptom_limits_length(self):
        # CATCHES: no length limit — potential DoS with extremely long strings
        long_symptom = "a" * 500
        result = sanitize_urgent_symptom(long_symptom)
        assert len(result) <= 200

    def test_sanitize_urgent_symptom_removes_special_characters(self):
        # CATCHES: injection risk — special characters like < > & should be stripped
        result = sanitize_urgent_symptom("brain fog <script>alert('xss')</script>")
        assert "<" not in result
        assert ">" not in result
        assert "'" not in result  # Single quotes removed
        assert "brain fog" in result

    def test_sanitize_urgent_symptom_allows_valid_characters(self):
        # CATCHES: overly aggressive sanitization breaking valid input
        result = sanitize_urgent_symptom("Hot flashes (night sweats), fatigue.")
        assert result == "Hot flashes (night sweats), fatigue."

    def test_sanitize_urgent_symptom_strips_whitespace(self):
        # CATCHES: leading/trailing whitespace not trimmed — affects matching
        result = sanitize_urgent_symptom("  brain fog  ")
        assert result == "brain fog"

    def test_urgent_symptom_sanitized_before_use_in_select_scenarios(self):
        # CATCHES: urgent_symptom used directly without sanitization
        svc = self._make_service()
        ctx = self._context(
            AppointmentGoal.urgent_symptom,
            urgent="brain fog <script>alert('xss')</script>",
        )
        scenarios = svc._select_scenarios(ctx, "perimenopause")
        # Should still match cognitive scenarios despite sanitization
        titles = self._titles(scenarios)
        assert any("brain fog" in t.lower() or "cognitive" in t.lower() for t in titles)
