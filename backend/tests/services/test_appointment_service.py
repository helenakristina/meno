"""Unit tests for AppointmentService.

Tests generate_narrative(), generate_scenarios(), and generate_pdf() in isolation
— all dependencies are mocked so no DB or LLM calls are made.
"""

from unittest.mock import AsyncMock, MagicMock
from datetime import date

import pytest

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.appointment import (
    AppointmentContext,
    AppointmentGoal,
    AppointmentPrepGenerateResponse,
    AppointmentPrepNarrativeResponse,
    AppointmentPrepScenariosResponse,
    AppointmentType,
    DismissalExperience,
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
    mock.save_scenarios.return_value = None
    mock.get_symptom_reference.return_value = {
        "sym-1": {"name": "Hot flashes", "category": "vasomotor"},
        "sym-2": {"name": "Night sweats", "category": "vasomotor"},
    }
    mock.get_concerns.return_value = ["Discuss HRT options", "Ask about dosage"]
    mock.get_appointment_data.return_value = {
        "narrative": "Logs show frequent hot flashes and night sweats.",
        "concerns": ["Discuss HRT options"],
        "scenarios": [{"id": "scenario-1", "title": "HRT risk", "suggestion": "..."}],
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
    provider = AsyncMock()
    provider.chat_completion.return_value = "Generated narrative text."
    svc = MagicMock()
    svc.provider = provider
    svc.generate_scenario_suggestions = AsyncMock(
        return_value='[{"suggestion": "You can advocate for treatment by citing NAMS guidelines.", "sources": []}]'
    )
    svc.generate_pdf_content = AsyncMock(
        return_value="## Provider Summary\n\nKey findings."
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
    mock.markdown_to_pdf.return_value = b"%PDF-mock"
    return mock


@pytest.fixture
def service(
    mock_appointment_repo,
    mock_symptoms_repo,
    mock_user_repo,
    mock_llm_service,
    mock_storage_service,
    mock_pdf_service,
):
    return AppointmentService(
        appointment_repo=mock_appointment_repo,
        symptoms_repo=mock_symptoms_repo,
        user_repo=mock_user_repo,
        llm_service=mock_llm_service,
        storage_service=mock_storage_service,
        pdf_service=mock_pdf_service,
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
        await service.generate_narrative("appt-123", "user-456", days_back=60)

        mock_llm_service.provider.chat_completion.assert_called_once()
        call_kwargs = mock_llm_service.provider.chat_completion.call_args[1]
        assert call_kwargs["max_tokens"] == 600
        assert call_kwargs["temperature"] == 0.3

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
        mock_llm_service.provider.chat_completion.side_effect = TimeoutError()

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_narrative("appt-123", "user-456", days_back=60)

    @pytest.mark.asyncio
    async def test_raises_database_error_when_llm_fails(
        self, service, mock_llm_service
    ):
        mock_llm_service.provider.chat_completion.side_effect = Exception("API error")

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
        await service.generate_pdf("appt-123", "user-456")

        assert mock_llm_service.generate_pdf_content.call_count == 2
        call_types = [
            c[1]["content_type"]
            for c in mock_llm_service.generate_pdf_content.call_args_list
        ]
        assert "provider_summary" in call_types
        assert "personal_cheatsheet" in call_types

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
        mock_llm_service.generate_pdf_content.side_effect = TimeoutError()

        with pytest.raises(DatabaseError, match="timed out"):
            await service.generate_pdf("appt-123", "user-456")

    @pytest.mark.asyncio
    async def test_raises_database_error_when_upload_fails(
        self, service, mock_storage_service
    ):
        mock_storage_service.upload_pdf.side_effect = Exception("S3 unavailable")

        with pytest.raises(DatabaseError, match="upload"):
            await service.generate_pdf("appt-123", "user-456")


# ---------------------------------------------------------------------------
# _select_scenarios (private helper)
# ---------------------------------------------------------------------------


class TestSelectScenarios:
    def _make_service(self):
        """Create service instance without initializing deps."""
        return AppointmentService.__new__(AppointmentService)

    def _context(self, goal, dismissed=DismissalExperience.once_or_twice, urgent=None):
        return AppointmentContext(
            appointment_type=AppointmentType.established_relationship,
            goal=goal,
            dismissed_before=dismissed,
            urgent_symptom=urgent,
        )

    def test_explore_hrt_selects_hrt_scenarios(self):
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")

        assert any(
            "hormone therapy" in s.lower() or "breast cancer" in s.lower()
            for s in scenarios
        )

    def test_urgent_hot_flash_selects_vasomotor_scenarios(self):
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="hot flashes")
        scenarios = svc._select_scenarios(ctx, "perimenopause")

        assert any(
            "hot flash" in s.lower() or "vasomotor" in s.lower() or "layer" in s.lower()
            for s in scenarios
        )

    def test_result_is_deduplicated(self):
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.explore_hrt)
        scenarios = svc._select_scenarios(ctx, "perimenopause")

        assert len(scenarios) == len(set(scenarios))

    def test_result_has_at_most_7_scenarios(self):
        svc = self._make_service()
        ctx = self._context(AppointmentGoal.urgent_symptom, urgent="brain fog")
        scenarios = svc._select_scenarios(ctx, "perimenopause")

        assert len(scenarios) <= 7


# ---------------------------------------------------------------------------
# _get_scenario_category (private helper)
# ---------------------------------------------------------------------------


class TestGetScenarioCategory:
    def _make_service(self):
        return AppointmentService.__new__(AppointmentService)

    def test_hormone_therapy_risk_returns_hrt_safety(self):
        svc = self._make_service()
        assert (
            svc._get_scenario_category("Hormone therapy increases breast cancer risk")
            == "hrt-safety"
        )

    def test_aging_normalization_returns_normalization(self):
        svc = self._make_service()
        assert svc._get_scenario_category("That's just normal aging") == "normalization"

    def test_antidepressant_returns_wrong_specialist(self):
        svc = self._make_service()
        assert (
            svc._get_scenario_category("Let's try an antidepressant first")
            == "wrong-specialist"
        )

    def test_unknown_returns_general(self):
        svc = self._make_service()
        assert svc._get_scenario_category("This is an unknown scenario") == "general"
