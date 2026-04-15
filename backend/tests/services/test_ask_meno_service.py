"""Unit tests for AskMenoService.

Tests ask(), get_suggested_prompts(), list_conversations(), get_conversation(),
and delete_conversation() in isolation — all dependencies are mocked.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.chat import Citation
from app.models.symptoms import SymptomDetail, SymptomLogResponse
from app.services.ask_meno import AskMenoService


USER_ID = "user-test-uuid"
CONVERSATION_UUID = UUID("11111111-1111-1111-1111-111111111111")

SAMPLE_CHUNKS = [
    {
        "id": "chunk-1",
        "content": "Hot flashes are a common vasomotor symptom.",
        "title": "Perimenopause Overview",
        "source_url": "https://menopausewiki.ca/hot-flashes",
        "source_type": "wiki",
        "section_name": "Vasomotor Symptoms",
        "similarity": 0.92,
    }
]

# The final rendered response text (after citation rendering)
LLM_RESPONSE = "Hot flashes are common during perimenopause. [Source 1]"

# The raw JSON string returned by the LLM (v2 structured output mode)
LLM_RAW_JSON = json.dumps(
    {
        "sections": [
            {
                "heading": None,
                "body": "Hot flashes are common during perimenopause.",
                "source_index": 1,
            }
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user_repo():
    mock = AsyncMock()
    mock.get_context.return_value = ("perimenopause", 48)
    return mock


@pytest.fixture
def mock_symptoms_repo():
    mock = AsyncMock()
    mock.get_summary.return_value = (
        "Most frequent symptoms last 30 days: hot flashes 10x"
    )
    return mock


@pytest.fixture
def mock_conversation_repo():
    mock = AsyncMock()
    mock.load.return_value = []
    mock.save.return_value = CONVERSATION_UUID
    return mock


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.chat_completion = AsyncMock(return_value=LLM_RAW_JSON)
    return service


@pytest.fixture
def mock_citation_service():
    svc = MagicMock()
    # Structured path (primary)
    _citation = Citation(
        url="https://menopausewiki.ca/hot-flashes",
        title="Perimenopause Overview",
        section="Vasomotor Symptoms",
        source_index=1,
    )
    svc.render_structured_response.return_value = (LLM_RESPONSE, [_citation])
    svc.extract.return_value = [_citation]
    return svc


@pytest.fixture
def mock_rag_retriever():
    return AsyncMock(return_value=SAMPLE_CHUNKS)


@pytest.fixture
def service(
    mock_user_repo,
    mock_symptoms_repo,
    mock_conversation_repo,
    mock_llm_service,
    mock_citation_service,
    mock_rag_retriever,
):
    return AskMenoService(
        user_repo=mock_user_repo,
        symptoms_repo=mock_symptoms_repo,
        conversation_repo=mock_conversation_repo,
        llm_service=mock_llm_service,
        citation_service=mock_citation_service,
        rag_retriever=mock_rag_retriever,
    )


# ---------------------------------------------------------------------------
# ask() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_returns_chat_response(service):
    result = await service.ask(USER_ID, "What causes hot flashes?")

    assert result.message == LLM_RESPONSE
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://menopausewiki.ca/hot-flashes"
    assert result.conversation_id == CONVERSATION_UUID


@pytest.mark.asyncio
async def test_ask_with_existing_conversation_loads_messages(
    service, mock_conversation_repo
):
    existing = [{"role": "user", "content": "previous question", "citations": []}]
    mock_conversation_repo.load.return_value = existing

    await service.ask(USER_ID, "Follow-up question", CONVERSATION_UUID)

    mock_conversation_repo.load.assert_called_once_with(CONVERSATION_UUID, USER_ID)


@pytest.mark.asyncio
async def test_ask_without_conversation_id_skips_load(service, mock_conversation_repo):
    await service.ask(USER_ID, "New question", conversation_id=None)

    mock_conversation_repo.load.assert_not_called()


@pytest.mark.asyncio
async def test_ask_persists_conversation(service, mock_conversation_repo):
    await service.ask(USER_ID, "What is HRT?")

    mock_conversation_repo.save.assert_called_once()
    saved_args = mock_conversation_repo.save.call_args
    messages = saved_args[0][2]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is HRT?"
    assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_ask_deduplicates_chunks(
    service, mock_rag_retriever, mock_citation_service
):
    duplicate_chunks = [
        {
            "id": "chunk-1",
            "source_url": "https://menopausewiki.ca/hot-flashes",
            "section_name": "Vasomotor",
        },
        {
            "id": "chunk-2",
            "source_url": "https://menopausewiki.ca/hot-flashes",
            "section_name": "Vasomotor",
        },
        {
            "id": "chunk-3",
            "source_url": "https://menopausewiki.ca/hrt",
            "section_name": "HRT",
        },
    ]
    mock_rag_retriever.return_value = duplicate_chunks

    await service.ask(USER_ID, "Tell me about symptoms")

    # render_structured_response should receive 2 unique chunks (deduped from 3)
    call_args = mock_citation_service.render_structured_response.call_args[0]
    assert len(call_args[1]) == 2


# ---------------------------------------------------------------------------
# ask() — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_raises_database_error_when_user_context_fails(
    service, mock_user_repo
):
    mock_user_repo.get_context.side_effect = Exception("DB connection error")

    with pytest.raises(DatabaseError, match="Failed to process question"):
        await service.ask(USER_ID, "What causes hot flashes?")


@pytest.mark.asyncio
async def test_ask_raises_database_error_when_symptom_summary_fails(
    service, mock_symptoms_repo
):
    mock_symptoms_repo.get_summary.side_effect = Exception("Timeout")

    with pytest.raises(DatabaseError, match="Failed to process question"):
        await service.ask(USER_ID, "What causes hot flashes?")


@pytest.mark.asyncio
async def test_ask_degrades_gracefully_when_rag_fails(
    service, mock_rag_retriever, mock_llm_service
):
    """RAG failure should degrade to no-source response, not raise."""
    mock_rag_retriever.side_effect = Exception("pgvector unavailable")

    result = await service.ask(USER_ID, "What is perimenopause?")

    # Should still return a response (LLM called with empty chunks)
    assert result.message == LLM_RESPONSE
    mock_llm_service.chat_completion.assert_called_once()


@pytest.mark.asyncio
async def test_ask_raises_database_error_when_llm_fails(service, mock_llm_service):
    mock_llm_service.chat_completion.side_effect = Exception("LLM timeout")

    with pytest.raises(DatabaseError, match="LLM call failed"):
        await service.ask(USER_ID, "What causes hot flashes?")


@pytest.mark.asyncio
async def test_ask_raises_database_error_when_conversation_save_fails(
    service, mock_conversation_repo
):
    mock_conversation_repo.save.side_effect = Exception("Write failed")

    with pytest.raises(DatabaseError, match="Failed to save conversation"):
        await service.ask(USER_ID, "What causes hot flashes?")


# ---------------------------------------------------------------------------
# ask() — empty RAG results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_with_empty_rag_results_still_calls_llm(
    service, mock_rag_retriever, mock_llm_service
):
    mock_rag_retriever.return_value = []

    result = await service.ask(USER_ID, "What is perimenopause?")

    mock_llm_service.chat_completion.assert_called_once()
    assert result.message == LLM_RESPONSE


# ---------------------------------------------------------------------------
# get_suggested_prompts()
# ---------------------------------------------------------------------------


def _make_log(log_id: str, symptoms: list[SymptomDetail]) -> SymptomLogResponse:
    return SymptomLogResponse(
        id=log_id,
        user_id=USER_ID,
        logged_at=datetime.now(timezone.utc),
        symptoms=symptoms,
        free_text_entry=None,
        source="cards",
    )


@pytest.mark.asyncio
async def test_get_suggested_prompts_with_recent_symptoms(service, mock_symptoms_repo):
    logs = [
        _make_log(
            "log-1",
            [
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-2", name="Night sweats", category="vasomotor"),
            ],
        ),
        _make_log(
            "log-2",
            [
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
            ],
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 2)

    result = await service.get_suggested_prompts(user_id=USER_ID)

    assert isinstance(result.prompts, list)
    assert 0 < len(result.prompts) <= 6
    prompts_text = " ".join(result.prompts).lower()
    assert any(
        term in prompts_text for term in ["hot flash", "brain fog", "night sweat"]
    )


@pytest.mark.asyncio
async def test_get_suggested_prompts_returns_at_most_max(service, mock_symptoms_repo):
    logs = [
        _make_log(
            "log-1",
            [
                SymptomDetail(id=f"id-{i}", name=name, category="cat")
                for i, name in enumerate(
                    [
                        "Hot flashes",
                        "Night sweats",
                        "Brain fog",
                        "Fatigue",
                        "Anxiety",
                        "Insomnia",
                        "Joint pain",
                        "Headaches",
                    ]
                )
            ],
        )
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    result = await service.get_suggested_prompts(user_id=USER_ID)
    assert len(result.prompts) == 6

    result3 = await service.get_suggested_prompts(user_id=USER_ID, max_prompts=3)
    assert len(result3.prompts) <= 3


@pytest.mark.asyncio
async def test_get_suggested_prompts_no_duplicates(service, mock_symptoms_repo):
    logs = [
        _make_log(
            "log-1",
            [
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
            ],
        )
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    result = await service.get_suggested_prompts(user_id=USER_ID)
    prompts = result.prompts
    assert len(prompts) == len(set(prompts))


@pytest.mark.asyncio
async def test_get_suggested_prompts_raises_database_error(service, mock_symptoms_repo):
    mock_symptoms_repo.get_logs.side_effect = DatabaseError("Query failed")

    with pytest.raises(DatabaseError):
        await service.get_suggested_prompts(user_id=USER_ID)


@pytest.mark.asyncio
async def test_get_suggested_prompts_wraps_unexpected_error(
    service, mock_symptoms_repo
):
    mock_symptoms_repo.get_logs.side_effect = Exception("Unexpected")

    with pytest.raises(DatabaseError, match="Failed to generate prompts"):
        await service.get_suggested_prompts(user_id=USER_ID)


@pytest.mark.asyncio
async def test_get_suggested_prompts_respects_days_back(service, mock_symptoms_repo):
    mock_symptoms_repo.get_logs.return_value = ([], 0)

    await service.get_suggested_prompts(user_id=USER_ID, days_back=7)

    call_args = mock_symptoms_repo.get_logs.call_args
    assert call_args[1]["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_get_suggested_prompts_handles_empty_symptom_lists(
    service, mock_symptoms_repo
):
    logs = [
        _make_log("log-1", []),  # Empty symptoms
        _make_log(
            "log-2",
            [SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor")],
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 2)

    result = await service.get_suggested_prompts(user_id=USER_ID)

    assert len(result.prompts) > 0


@pytest.mark.asyncio
async def test_get_suggested_prompts_caches_config(service, mock_symptoms_repo):
    mock_symptoms_repo.get_logs.return_value = ([], 0)

    await service.get_suggested_prompts(user_id=USER_ID)
    await service.get_suggested_prompts(user_id="user-other")

    assert service._prompt_config is not None


# ---------------------------------------------------------------------------
# list_conversations()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_returns_response(service, mock_conversation_repo):
    mock_conversation_repo.list.return_value = (
        [
            {
                "id": str(CONVERSATION_UUID),
                "created_at": "2026-03-13T10:00:00Z",
                "messages": [{"role": "user", "content": "Hello", "citations": []}],
            }
        ],
        1,
    )

    result = await service.list_conversations(USER_ID, limit=20, offset=0)

    assert result.total == 1
    assert len(result.conversations) == 1
    assert result.conversations[0].id == CONVERSATION_UUID
    assert result.conversations[0].message_count == 1
    assert not result.has_more


@pytest.mark.asyncio
async def test_list_conversations_has_more(service, mock_conversation_repo):
    rows = [
        {
            "id": str(CONVERSATION_UUID),
            "created_at": "2026-03-13T10:00:00Z",
            "messages": [],
        }
    ]
    mock_conversation_repo.list.return_value = (rows, 50)

    result = await service.list_conversations(USER_ID, limit=20, offset=0)

    assert result.has_more is True
    assert result.total == 50


@pytest.mark.asyncio
async def test_list_conversations_empty(service, mock_conversation_repo):
    mock_conversation_repo.list.return_value = ([], 0)

    result = await service.list_conversations(USER_ID, limit=20, offset=0)

    assert result.total == 0
    assert result.conversations == []
    assert not result.has_more


# ---------------------------------------------------------------------------
# get_conversation()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conversation_returns_messages(service, mock_conversation_repo):
    mock_conversation_repo.load.return_value = [
        {"role": "user", "content": "Hello", "citations": []},
        {"role": "assistant", "content": "Hi there!", "citations": []},
    ]

    result = await service.get_conversation(CONVERSATION_UUID, USER_ID)

    assert result.conversation_id == CONVERSATION_UUID
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"
    assert result.messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_get_conversation_not_found_raises(service, mock_conversation_repo):
    mock_conversation_repo.load.side_effect = EntityNotFoundError("Not found")

    with pytest.raises(EntityNotFoundError):
        await service.get_conversation(CONVERSATION_UUID, USER_ID)


# ---------------------------------------------------------------------------
# delete_conversation()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_conversation_calls_repo(service, mock_conversation_repo):
    await service.delete_conversation(CONVERSATION_UUID, USER_ID)

    mock_conversation_repo.delete.assert_called_once_with(CONVERSATION_UUID, USER_ID)


@pytest.mark.asyncio
async def test_delete_conversation_not_found_raises(service, mock_conversation_repo):
    mock_conversation_repo.delete.side_effect = EntityNotFoundError("Not found")

    with pytest.raises(EntityNotFoundError):
        await service.delete_conversation(CONVERSATION_UUID, USER_ID)


# ---------------------------------------------------------------------------
# v1 JSON format regression test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_json_from_llm_raises_exception(
    mock_user_repo,
    mock_symptoms_repo,
    mock_conversation_repo,
    mock_citation_service,
    mock_rag_retriever,
):
    """CATCHES: malformed LLM JSON silently swallowed instead of raising.

    The structured response pipeline has confirmed reliability in production.
    Failures must surface as errors — not degrade silently.
    """
    llm_service = MagicMock()
    llm_service.chat_completion = AsyncMock(return_value="not valid json {{")

    svc = AskMenoService(
        user_repo=mock_user_repo,
        symptoms_repo=mock_symptoms_repo,
        conversation_repo=mock_conversation_repo,
        llm_service=llm_service,
        citation_service=mock_citation_service,
        rag_retriever=mock_rag_retriever,
    )

    with pytest.raises(Exception):
        await svc.ask(USER_ID, "What causes hot flashes?")
