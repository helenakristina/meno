"""Tests for POST /api/chat.

Supabase is mocked via FastAPI dependency_overrides (same pattern as test_symptoms.py).
OpenAI and RAG retrieval are patched so no real network calls are made.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.supabase import get_client
from app.main import app

# ---------------------------------------------------------------------------
# Constants & fixture data
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}
CONVERSATION_UUID = "11111111-1111-1111-1111-111111111111"

SAMPLE_USER_ROW = {
    "journey_stage": "perimenopause",
    "date_of_birth": "1975-06-15",
}

SAMPLE_SUMMARY_ROW = {
    "summary_text": "Most frequent symptoms last 30 days: fatigue 18x, brain fog 12x"
}

SAMPLE_CHUNKS = [
    {
        "id": "chunk-1",
        "content": "Hot flashes are a common vasomotor symptom of perimenopause.",
        "title": "Perimenopause Overview",
        "source_url": "https://menopausewiki.ca/hot-flashes",
        "source_type": "wiki",
        "section_name": "Vasomotor Symptoms",
        "similarity": 0.92,
    },
    {
        "id": "chunk-2",
        "content": "Current Menopause Society guidelines support HRT for most healthy women.",
        "title": "HRT Guidelines 2023",
        "source_url": "https://menopause.org/hrt-guidelines",
        "source_type": "wiki",
        "section_name": "HRT Safety",
        "similarity": 0.85,
    },
]

# All LLM responses must now be valid v2 structured JSON.
# The fallback free-text pipeline was removed — the primary path is render_structured_response.

# Single-section response citing source 1
V2_OPENAI_RESPONSE = json.dumps(
    {
        "sections": [
            {
                "heading": "Hot Flashes",
                "body": "Hot flashes are one of the most common symptoms of perimenopause.",
                "source_index": 1,
            }
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)

# Two-section response citing sources 1 and 2
V2_TWO_SOURCE_RESPONSE = json.dumps(
    {
        "sections": [
            {
                "heading": None,
                "body": "Hot flashes affect up to 80% of women during perimenopause.",
                "source_index": 1,
            },
            {
                "heading": None,
                "body": "Current guidelines support hormone therapy for eligible women.",
                "source_index": 2,
            },
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)

# Response with no source citations
V2_NO_CITATIONS_RESPONSE = json.dumps(
    {
        "sections": [
            {
                "heading": None,
                "body": "I'm only able to help with menopause and perimenopause education.",
                "source_index": None,
            }
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)

# Response where both sections cite the same source (deduplication test)
V2_DUPLICATE_SOURCE_RESPONSE = json.dumps(
    {
        "sections": [
            {
                "heading": None,
                "body": "Hot flashes are common vasomotor symptoms.",
                "source_index": 1,
            },
            {
                "heading": None,
                "body": "They are the most frequently reported symptom.",
                "source_index": 1,
            },
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)

# Response with an out-of-range source_index (phantom citation equivalent)
V2_PHANTOM_SOURCE_RESPONSE = json.dumps(
    {
        "sections": [
            {
                "heading": None,
                "body": "Hot flashes are common.",
                "source_index": 1,
            },
            {
                "heading": None,
                "body": "HRT is a treatment option.",
                "source_index": 2,
            },
            {
                "heading": None,
                "body": "Additional research suggests other options.",
                "source_index": 3,  # out of range — only 2 chunks available
            },
        ],
        "disclaimer": None,
        "insufficient_sources": False,
    }
)


# ---------------------------------------------------------------------------
# Mock helpers (follows the same MagicMock-based pattern as test_symptoms.py)
# ---------------------------------------------------------------------------


class MockQueryBuilder:
    """Fluent builder that supports arbitrary method chaining + async execute()."""

    def __init__(self, data=None):
        self._data = data if data is not None else []

    def select(self, *_, **__):
        return self

    def insert(self, *_, **__):
        return self

    def update(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_, **__):
        return self

    async def execute(self):
        result = MagicMock()
        result.data = self._data
        return result


def make_mock_client(
    user_data=None,
    summary_data=None,
    conversation_load_data=None,
    conversation_save_data=None,
    auth_error: Exception | None = None,
) -> MagicMock:
    """Build a mock Supabase client (MagicMock base, AsyncMock for auth)."""
    mock = MagicMock()

    if auth_error:
        mock.auth.get_user = AsyncMock(side_effect=auth_error)
    else:
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id=USER_ID))
        )

    _user_data = user_data if user_data is not None else [SAMPLE_USER_ROW]
    _summary_data = summary_data if summary_data is not None else [SAMPLE_SUMMARY_ROW]
    _conv_load = (
        conversation_load_data
        if conversation_load_data is not None
        else [{"id": CONVERSATION_UUID, "messages": "[]"}]
    )
    _conv_save = (
        conversation_save_data
        if conversation_save_data is not None
        else [{"id": CONVERSATION_UUID, "messages": "[]"}]
    )

    # Track which call we're on for conversations table (load vs save)
    conv_call_count = {"n": 0}

    def table_side_effect(table_name):
        if table_name == "users":
            return MockQueryBuilder(data=_user_data)
        if table_name == "symptom_summary_cache":
            return MockQueryBuilder(data=_summary_data)
        if table_name == "conversations":
            # First access is a load (select), subsequent are saves (insert/update)
            n = conv_call_count["n"]
            conv_call_count["n"] += 1
            if n == 0:
                return MockQueryBuilder(data=_conv_load)
            return MockQueryBuilder(data=_conv_save)
        return MockQueryBuilder()

    mock.table.side_effect = table_side_effect
    return mock


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


def _make_openai_response(text: str):
    """Create a mock OpenAI response object."""
    usage = MagicMock()
    usage.prompt_tokens = 300
    usage.completion_tokens = 120
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_provider_response(text: str) -> tuple[str, int, int]:
    """Create a mock OpenAIProvider response tuple."""
    return text, 300, 120


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_chat_requires_auth(client):
    # Mock needed: FastAPI instantiates get_client during DI even when auth fails on a
    # missing header, so without an override the real Supabase client raises
    # SupabaseException before the 401 can be returned.
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        response = client.post(
            "/api/chat", json={"message": "What causes hot flashes?"}
        )
        assert response.status_code == 401
    finally:
        clear()


def test_chat_rejects_invalid_token(client):
    mock_client = make_mock_client(auth_error=Exception("Invalid token"))
    clear = override(mock_client)
    try:
        response = client.post(
            "/api/chat",
            json={"message": "What causes hot flashes?"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 401
    finally:
        clear()


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_chat_rejects_empty_message(client):
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_OPENAI_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "   "},
                headers=AUTH_HEADER,
            )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    finally:
        clear()


def test_chat_rejects_missing_message_field(client):
    """Pydantic validation error (422) for payload missing required 'message' field."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        response = client.post("/api/chat", json={}, headers=AUTH_HEADER)
        assert response.status_code == 422
    finally:
        clear()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_chat_success_returns_message_and_citations(client):
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_TWO_SOURCE_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes hot flashes?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        assert "hot flashes" in body["message"].lower()
        assert len(body["citations"]) == 2
        assert body["citations"][0]["url"] == "https://menopausewiki.ca/hot-flashes"
        assert body["citations"][0]["title"] == "Perimenopause Overview"
        assert body["citations"][1]["url"] == "https://menopause.org/hrt-guidelines"
        assert "conversation_id" in body
    finally:
        clear()


def test_chat_deduplicates_citations(client):
    """Multiple sections citing the same source_index produce one citation entry."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_DUPLICATE_SOURCE_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "Tell me about hot flashes"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["citations"]) == 1
        assert body["citations"][0]["url"] == "https://menopausewiki.ca/hot-flashes"
    finally:
        clear()


def test_chat_returns_empty_citations_when_no_sources_cited(client):
    """Response with source_index=None in all sections produces an empty citations list."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_NO_CITATIONS_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What's the weather today?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["citations"] == []
    finally:
        clear()


def test_chat_when_llm_returns_v2_json_then_structured_path_exercised(client):
    """LLM returning valid v2 JSON exercises render_structured_response, not the fallback."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_OPENAI_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes hot flashes?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # The structured body text should appear in the rendered prose paragraph
        assert (
            "Hot flashes are one of the most common symptoms of perimenopause."
            in body["message"]
        )
        # source_index=1 resolves to SAMPLE_CHUNKS[0], so citations must be non-empty
        assert len(body["citations"]) >= 1
        assert body["citations"][0]["url"] == "https://menopausewiki.ca/hot-flashes"
    finally:
        clear()


# ---------------------------------------------------------------------------
# Conversation storage
# ---------------------------------------------------------------------------


def test_chat_creates_new_conversation_when_no_id_provided(client):
    mock_client = make_mock_client(
        conversation_save_data=[{"id": CONVERSATION_UUID, "messages": "[]"}]
    )
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=[]),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_OPENAI_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What is perimenopause?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["conversation_id"] == CONVERSATION_UUID
    finally:
        clear()


def test_chat_404_for_unknown_conversation_id(client):
    # conversations table returns empty for the load query
    mock_client = make_mock_client(conversation_load_data=[])
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "message": "What is perimenopause?",
                    "conversation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                },
                headers=AUTH_HEADER,
            )

        assert response.status_code == 404
    finally:
        clear()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_chat_degrades_gracefully_when_rag_fails(client):
    """RAG retrieval failure should not crash the endpoint — degrade to no sources."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(side_effect=Exception("pgvector unavailable")),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_NO_CITATIONS_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What is perimenopause?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
    finally:
        clear()


def test_chat_500_when_openai_fails(client):
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.side_effect = Exception("OpenAI API error")
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What is perimenopause?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 500
        assert "temporarily unavailable" in response.json()["detail"]
    finally:
        clear()


# ---------------------------------------------------------------------------
# User context fallback
# ---------------------------------------------------------------------------


def test_chat_uses_defaults_when_user_profile_missing(client):
    """Missing user profile gracefully falls back to journey_stage='unsure', age=None."""
    mock_client = make_mock_client(user_data=[])  # no profile row
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_OPENAI_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes brain fog?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
    finally:
        clear()


def test_chat_uses_default_summary_when_cache_missing(client):
    """Missing symptom summary cache falls back to 'No symptom data logged yet.'"""
    mock_client = make_mock_client(summary_data=[])  # no cache row
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_OPENAI_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes brain fog?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
    finally:
        clear()


# ---------------------------------------------------------------------------
# Citation sanitization (phantom citation removal)
# ---------------------------------------------------------------------------


def test_chat_sanitizes_phantom_citations(client):
    """Out-of-range source_index in structured response produces no citation marker."""
    # V2_PHANTOM_SOURCE_RESPONSE has source_index: 3 but only 2 chunks available
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_PHANTOM_SOURCE_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What are my options for managing symptoms?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # out-of-range source_index (3) produces no [Source 3] marker in rendered text
        assert "[Source 3]" not in body["message"]
        # Valid source_index values produce markers
        assert "[Source 1]" in body["message"]
        assert "[Source 2]" in body["message"]
        # Citations should only include 2 entries (source_index 3 is out of range)
        assert len(body["citations"]) == 2
    finally:
        clear()


def test_chat_citations_include_section_names(client):
    """Citations include section names from chunk metadata when available."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = V2_TWO_SOURCE_RESPONSE
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes hot flashes and what about HRT?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        citations = body["citations"]

        # Check that section names are present in citations
        assert len(citations) == 2
        assert citations[0]["section"] == "Vasomotor Symptoms"
        assert citations[1]["section"] == "HRT Safety"
    finally:
        clear()


def test_chat_handles_multiple_phantom_citations(client):
    """Multiple out-of-range source indices are all dropped from rendered output."""
    response_json = json.dumps(
        {
            "sections": [
                {"heading": None, "body": "Hot flashes are common.", "source_index": 1},
                {
                    "heading": None,
                    "body": "Night sweats also occur.",
                    "source_index": 4,
                },
                {"heading": None, "body": "Brain fog is frequent.", "source_index": 5},
                {"heading": None, "body": "HRT may help.", "source_index": 2},
            ],
            "disclaimer": None,
            "insufficient_sources": False,
        }
    )
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = response_json
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "Tell me about symptoms"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # Out-of-range source indices (4 and 5) produce no markers
        assert "[Source 4]" not in body["message"]
        assert "[Source 5]" not in body["message"]
        # Valid source indices produce markers
        assert "[Source 1]" in body["message"]
        assert "[Source 2]" in body["message"]
        # Only 2 valid citations
        assert len(body["citations"]) == 2
    finally:
        clear()


def test_chat_malformed_json_from_llm_returns_500(client):
    """Malformed JSON from the LLM raises rather than silently degrading."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.dependencies.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.dependencies.OpenAIProvider") as MockProvider,
        ):
            mock_instance = AsyncMock()
            mock_instance.chat_completion.return_value = "not valid json {{"
            MockProvider.return_value = mock_instance

            response = client.post(
                "/api/chat",
                json={"message": "Tell me about symptoms"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 500
    finally:
        clear()
