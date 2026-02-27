"""Tests for POST /api/chat.

Supabase is mocked via FastAPI dependency_overrides (same pattern as test_symptoms.py).
OpenAI and RAG retrieval are patched so no real network calls are made.
"""
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

OPENAI_RESPONSE = (
    "Hot flashes affect up to 80% of women during perimenopause [Source 1]. "
    "Current guidelines support hormone therapy for eligible women [Source 2]."
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
    _conv_load = conversation_load_data if conversation_load_data is not None else [
        {"id": CONVERSATION_UUID, "messages": "[]"}
    ]
    _conv_save = conversation_save_data if conversation_save_data is not None else [
        {"id": CONVERSATION_UUID, "messages": "[]"}
    ]

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
    usage = MagicMock()
    usage.prompt_tokens = 300
    usage.completion_tokens = 120
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


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
    response = client.post("/api/chat", json={"message": "What causes hot flashes?"})
    assert response.status_code == 401


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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

            response = client.post(
                "/api/chat",
                json={"message": "What causes hot flashes?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == OPENAI_RESPONSE
        assert len(body["citations"]) == 2
        assert body["citations"][0]["url"] == "https://menopausewiki.ca/hot-flashes"
        assert body["citations"][0]["title"] == "Perimenopause Overview"
        assert body["citations"][1]["url"] == "https://menopause.org/hrt-guidelines"
        assert "conversation_id" in body
    finally:
        clear()


def test_chat_deduplicates_citations(client):
    """Multiple [Source 1] references in the response produce one citation entry."""
    response_text = (
        "Hot flashes are common [Source 1]. They are vasomotor symptoms [Source 1]."
    )
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(response_text)
            MockOpenAI.return_value = instance

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
    """Response with no [Source N] references produces an empty citations list."""
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(
                "I'm only able to help with menopause and perimenopause education."
            )
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=[]),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(side_effect=Exception("pgvector unavailable")),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(
                "I can share general information about perimenopause."
            )
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.side_effect = Exception("OpenAI API error")
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

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
    """Phantom citations like [Source 3] when only 2 sources exist are removed."""
    # Response references [Source 3] but only 2 sources are provided
    response_text = (
        "Hot flashes are common [Source 1]. "
        "HRT is an option [Source 2]. "
        "Additional research shows more options [Source 3]."
    )
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(response_text)
            MockOpenAI.return_value = instance

            response = client.post(
                "/api/chat",
                json={"message": "What are my options for managing symptoms?"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # The message should have [Source 3] removed
        assert "[Source 3]" not in body["message"]
        # But [Source 1] and [Source 2] should remain
        assert "[Source 1]" in body["message"]
        assert "[Source 2]" in body["message"]
        # Citations should only include 2 entries
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
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(OPENAI_RESPONSE)
            MockOpenAI.return_value = instance

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
    """Multiple phantom citations are all removed."""
    response_text = (
        "Hot flashes [Source 1]. "
        "Night sweats [Source 4]. "
        "Brain fog [Source 5]. "
        "HRT [Source 2]."
    )
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(response_text)
            MockOpenAI.return_value = instance

            response = client.post(
                "/api/chat",
                json={"message": "Tell me about symptoms"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # Phantom citations [Source 4] and [Source 5] should be removed
        assert "[Source 4]" not in body["message"]
        assert "[Source 5]" not in body["message"]
        # Valid citations should remain
        assert "[Source 1]" in body["message"]
        assert "[Source 2]" in body["message"]
        # Only 2 valid citations
        assert len(body["citations"]) == 2
    finally:
        clear()


def test_chat_sanitizes_plain_bracket_phantom_citations(client):
    """Phantom citations using plain [N] format are also removed."""
    # Response uses plain [N] format instead of [Source N]
    response_text = (
        "Hot flashes affect women [1]. "
        "Some researchers found [4]. "
        "HRT options include [2]."
    )
    mock_client = make_mock_client()
    clear = override(mock_client)
    try:
        with (
            patch(
                "app.api.routes.chat.retrieve_relevant_chunks",
                new=AsyncMock(return_value=SAMPLE_CHUNKS),
            ),
            patch("app.api.routes.chat.AsyncOpenAI") as MockOpenAI,
        ):
            instance = AsyncMock()
            instance.chat.completions.create.return_value = _make_openai_response(response_text)
            MockOpenAI.return_value = instance

            response = client.post(
                "/api/chat",
                json={"message": "Tell me about symptoms"},
                headers=AUTH_HEADER,
            )

        assert response.status_code == 200
        body = response.json()
        # Phantom citation [4] should be removed
        assert "[4]" not in body["message"]
        # Valid citations should remain
        assert "[1]" in body["message"]
        assert "[2]" in body["message"]
        # Only 2 valid citations
        assert len(body["citations"]) == 2
    finally:
        clear()
