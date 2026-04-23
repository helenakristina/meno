"""Tests for CitationService.

Covers citation extraction, relevance checking, and structured response rendering.
All tests use pure inputs/outputs (no mocking needed).
"""

import logging

import pytest

from app.models.chat import ResponseSection, StructuredLLMResponse
from app.services.citations import CitationService


@pytest.fixture
def service():
    """Citation service instance (stateless, so can be reused)."""
    return CitationService()


@pytest.fixture
def sample_chunks():
    """Sample knowledge base chunks for testing."""
    return [
        {
            "source_url": "https://menopausewiki.ca/overview",
            "title": "Perimenopause Overview",
            "section_name": "Definition",
            "content": "Perimenopause is the transition to menopause.",
        },
        {
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/123456",
            "title": "Hot Flashes Research",
            "section_name": "Methods",
            "content": "A study of 500 participants found hot flashes common.",
        },
        {
            "source_url": "https://nams.org/hrt-guidelines",
            "title": "HRT Safety Guidelines",
            "section_name": "Recommendations",
            "content": "Current evidence supports HRT for eligible women.",
        },
    ]


# ---------------------------------------------------------------------------
# TestRenderStructuredResponse
# Tests for the v2 paragraph-based render_structured_response method.
# ---------------------------------------------------------------------------


class TestRenderStructuredResponse:
    """Tests for CitationService.render_structured_response() (v2 paragraph schema)."""

    # CATCHES: regression to bullet-point format after refactor
    def test_renders_paragraph_not_bullets(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="MHT is well-tolerated.", source_index=1),
            ]
        )
        rendered, _ = service.render_structured_response(structured, sample_chunks)
        assert "\n-" not in rendered
        assert "MHT is well-tolerated." in rendered

    # CATCHES: duplicate Citation objects created when same source used in two sections
    def test_deduplicates_citations_same_source(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    body="First paragraph about perimenopause.", source_index=1
                ),
                ResponseSection(
                    body="Second paragraph also about perimenopause.", source_index=1
                ),
            ]
        )
        _, citations = service.render_structured_response(structured, sample_chunks)
        assert len(citations) == 1
        assert citations[0].title == "Perimenopause Overview"

    # CATCHES: [Source N] marker appended to section with null source_index
    def test_null_source_index_no_citation_marker(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    body="Closing remarks with no source.", source_index=None
                ),
            ]
        )
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert "[Source" not in rendered
        assert len(citations) == 0

    # CATCHES: heading omitted when section.heading is None (OK), or shown when present
    def test_no_heading_when_null(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(heading=None, body="Body text.", source_index=1),
            ]
        )
        rendered, _ = service.render_structured_response(structured, sample_chunks)
        assert "###" not in rendered

    # CATCHES: heading not rendered above body when section.heading is set
    def test_heading_rendered_above_body(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    heading="HRT Overview", body="MHT is effective.", source_index=1
                ),
            ]
        )
        rendered, _ = service.render_structured_response(structured, sample_chunks)
        # Heading should appear as ### heading before the body paragraph
        assert "### HRT Overview" in rendered
        assert "MHT is effective." in rendered
        heading_pos = rendered.index("### HRT Overview")
        body_pos = rendered.index("MHT is effective.")
        assert heading_pos < body_pos

    # CATCHES: out-of-range source_index (e.g. 99) causes IndexError or exception
    def test_invalid_source_index_skipped_gracefully(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Body with bad source.", source_index=99),
            ]
        )
        # Should not raise; body is still rendered, no citation marker
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert "Body with bad source." in rendered
        assert "[Source" not in rendered
        assert len(citations) == 0

    # CATCHES: disclaimer appended even when it is None (extra blank line or text)
    def test_disclaimer_appended_when_present(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Main content.", source_index=1),
            ],
            disclaimer="My sources don't cover dosing specifics.",
        )
        rendered, _ = service.render_structured_response(structured, sample_chunks)
        assert "My sources don't cover dosing specifics." in rendered

    def test_when_disclaimer_is_none_then_no_disclaimer_text_appended(
        self, service, sample_chunks
    ):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Main content.", source_index=1),
            ],
            disclaimer=None,
        )
        rendered, _ = service.render_structured_response(structured, sample_chunks)
        # The rendered text must not contain any disclaimer paragraph.
        # A disclaimer would be appended after a double newline, so assert
        # neither of the sentinel phrases from render_structured_response appears.
        assert "\n\nI don't have" not in rendered
        assert "\n\nPlease consult" not in rendered
        # Also confirm the body content is present (sanity check)
        assert "Main content." in rendered

    # CATCHES: insufficient_sources flag bypassed, returning empty sections instead of disclaimer
    def test_insufficient_sources_short_circuits(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[],
            disclaimer="I don't have sources to answer that.",
            insufficient_sources=True,
        )
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert rendered == "I don't have sources to answer that."
        assert citations == []

    def test_insufficient_sources_default_message_when_no_disclaimer(
        self, service, sample_chunks
    ):
        structured = StructuredLLMResponse(
            sections=[],
            disclaimer=None,
            insufficient_sources=True,
        )
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert "don't have" in rendered.lower() or "not have" in rendered.lower()
        assert citations == []

    # CATCHES: multiple unique sources produce wrong number of Citation objects
    def test_multiple_unique_sources_all_included(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="About perimenopause.", source_index=1),
                ResponseSection(body="About hot flashes.", source_index=2),
                ResponseSection(body="About HRT.", source_index=3),
            ]
        )
        _, citations = service.render_structured_response(structured, sample_chunks)
        assert len(citations) == 3

    # CATCHES: empty body sections producing blank paragraphs
    def test_empty_body_sections_skipped(self, service, sample_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="   ", source_index=1),
                ResponseSection(body="Real content here.", source_index=2),
            ]
        )
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert "Real content here." in rendered
        assert len(citations) == 1

    # CATCHES: low-overlap section not producing a WARNING log (observability regression)
    def test_low_overlap_section_logs_warning(self, service, caplog):
        """A section whose body has low keyword overlap with its source chunk logs a WARNING."""
        chunks = [
            {
                "source_url": "https://example.com/sleep",
                "title": "Sleep Research",
                "section_name": "Results",
                "content": "sleep disruption insomnia nocturnal awakening REM reduction",
            }
        ]
        # Body is about a completely unrelated topic — zero overlap with chunk content
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    body="Ashwagandha supplements may reduce cortisol levels significantly.",
                    source_index=1,
                ),
            ]
        )
        with caplog.at_level(logging.WARNING, logger="app.services.citations"):
            service.render_structured_response(structured, chunks)

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("low overlap" in msg for msg in warning_messages), (
            f"Expected a 'low overlap' WARNING but got: {warning_messages}"
        )

    # CATCHES: two sections sharing the same out-of-range index causing IndexError or
    # inconsistent behaviour (e.g. first skipped, second resolved against wrong chunk)
    def test_when_two_sections_share_same_out_of_range_source_index_then_no_exception(
        self, service, sample_chunks
    ):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="First section body.", source_index=99),
                ResponseSection(body="Second section body.", source_index=99),
            ]
        )
        # Must not raise; both sections' bodies are rendered, no citation marker added
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        assert "First section body." in rendered
        assert "Second section body." in rendered
        assert "[Source" not in rendered
        assert len(citations) == 0

    def test_non_http_source_url_is_dropped(self, service):
        # CATCHES: A chunk with a non-HTTP source_url (e.g. javascript:alert(1)) is
        # included as a citation, creating an XSS vector in the rendered frontend output.
        chunks = [
            {
                "source_url": "javascript:alert(1)",
                "title": "Malicious Source",
                "section_name": "Intro",
                "content": "Perimenopause hot flashes are common vasomotor symptoms.",
            }
        ]
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    body="Hot flashes are common vasomotor symptoms.",
                    source_index=1,
                )
            ],
            insufficient_sources=False,
        )
        rendered, citations = service.render_structured_response(structured, chunks)
        assert citations == []
        assert "javascript:" not in rendered

    # CATCHES: empty-body + not insufficient_sources + no disclaimer falling into
    # wrong branch and returning empty string or raising
    def test_when_all_bodies_whitespace_and_insufficient_sources_false_and_no_disclaimer_then_fallback_message(
        self, service, sample_chunks
    ):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="   ", source_index=1),
                ResponseSection(body="\t\n", source_index=2),
            ],
            insufficient_sources=False,
            disclaimer=None,
        )
        rendered, citations = service.render_structured_response(
            structured, sample_chunks
        )
        # All bodies are whitespace so rendered_text is empty — falls into the
        # "all sections empty" branch and returns the hardcoded fallback message.
        assert "don't have" in rendered.lower() or "not have" in rendered.lower()
        assert citations == []
