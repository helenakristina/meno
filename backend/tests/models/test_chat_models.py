"""Tests for chat Pydantic models.

Validates the v2 paragraph-based response schema (ResponseSection +
StructuredLLMResponse) and ensures the old v1 claims-based format no longer
parses without error.
"""

import pytest
from pydantic import ValidationError

from app.models.chat import (
    ChatRequest,
    Citation,
    ResponseSection,
    StructuredLLMResponse,
)


class TestResponseSection:
    # CATCHES: ResponseSection missing from chat.py after refactor
    def test_minimal_valid_section(self):
        section = ResponseSection(body="Test paragraph.", source_index=1)
        assert section.body == "Test paragraph."
        assert section.source_index == 1
        assert section.heading is None

    def test_section_with_heading(self):
        section = ResponseSection(
            heading="HRT Overview", body="Body text.", source_index=2
        )
        assert section.heading == "HRT Overview"

    # CATCHES: null source_index rejected when it should be allowed (closing section)
    def test_null_source_index_allowed(self):
        section = ResponseSection(body="Closing remarks.", source_index=None)
        assert section.source_index is None

    # CATCHES: body field missing from model causes silent empty output
    def test_body_is_required(self):
        with pytest.raises(ValidationError):
            ResponseSection(source_index=1)  # type: ignore[call-arg]


class TestStructuredLLMResponse:
    # CATCHES: v2 JSON format from LLM not parseable after model update
    def test_v2_response_parses_correctly(self):
        data = {
            "sections": [
                {"heading": None, "body": "MHT is well-tolerated.", "source_index": 1},
                {
                    "heading": "Guidelines",
                    "body": "Current evidence supports MHT.",
                    "source_index": 2,
                },
            ],
            "disclaimer": None,
            "insufficient_sources": False,
        }
        response = StructuredLLMResponse(**data)
        assert len(response.sections) == 2
        assert response.sections[0].body == "MHT is well-tolerated."
        assert response.sections[1].heading == "Guidelines"

    def test_defaults_work(self):
        response = StructuredLLMResponse()
        assert response.sections == []
        assert response.disclaimer is None
        assert response.insufficient_sources is False

    def test_insufficient_sources_flag(self):
        response = StructuredLLMResponse(
            sections=[],
            disclaimer="No relevant sources found.",
            insufficient_sources=True,
        )
        assert response.insufficient_sources is True
        assert response.disclaimer == "No relevant sources found."

    # CATCHES: v1 claims-based format silently accepted instead of triggering fallback
    def test_v1_format_fails_validation(self):
        """Old schema with claims[] should fail because body is required."""
        v1_data = {
            "sections": [
                {
                    "heading": None,
                    "claims": [{"text": "Some claim.", "source_indices": [1]}],
                }
            ],
            "disclaimer": None,
            "insufficient_sources": False,
        }
        with pytest.raises(ValidationError):
            StructuredLLMResponse(**v1_data)


class TestUnchangedModels:
    """Smoke tests confirming the API contract models are unchanged."""

    def test_citation_model(self):
        c = Citation(url="https://example.com", title="Test Source")
        assert c.url == "https://example.com"
        assert c.title == "Test Source"
        assert c.section is None

    def test_chat_request_model(self):
        req = ChatRequest(message="What is MHT?")
        assert req.message == "What is MHT?"
        assert req.conversation_id is None
