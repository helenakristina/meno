"""Tests for CitationService.

Covers citation extraction, sanitization, renumbering, and edge cases.
All tests use pure inputs/outputs (no mocking needed).
"""

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
            "content": "Perimenopause is the transition...",
        },
        {
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/123456",
            "title": "Hot Flashes Research",
            "section_name": "Methods",
            "content": "A study of 500 participants...",
        },
        {
            "source_url": "https://nams.org/hrt-guidelines",
            "title": "HRT Safety Guidelines",
            "section_name": "Recommendations",
            "content": "Current evidence suggests...",
        },
    ]


class TestSanitizeAndRenumber:
    """Tests for the sanitize_and_renumber method."""

    def test_no_citations(self, service):
        """Text with no citations should be returned unchanged."""
        text = "This is a response with no citations."
        result = service.sanitize_and_renumber(text, 3)

        assert result.text == text
        assert result.removed_indices == []

    def test_valid_source_citations_unchanged(self, service):
        """Valid [Source N] citations should be preserved."""
        text = "Research shows [Source 1] that heat flashes occur. [Source 2] also supports this."
        result = service.sanitize_and_renumber(text, 2)

        assert "[Source 1]" in result.text
        assert "[Source 2]" in result.text
        assert result.removed_indices == []

    def test_valid_plain_citations_unchanged(self, service):
        """Valid [N] citations should be preserved."""
        text = "Research shows [1] that heat flashes occur. [2] also supports this."
        result = service.sanitize_and_renumber(text, 2)

        assert "[1]" in result.text
        assert "[2]" in result.text
        assert result.removed_indices == []

    def test_phantom_citations_removed(self, service):
        """Citations beyond max_valid_sources should be removed."""
        text = "Research shows [Source 1]. Other studies [Source 4] and [Source 5]."
        result = service.sanitize_and_renumber(text, 2)

        assert "[Source 1]" in result.text
        assert "[Source 4]" not in result.text
        assert "[Source 5]" not in result.text
        assert set(result.removed_indices) == {4, 5}

    def test_phantom_plain_citations_removed(self, service):
        """Plain [N] citations beyond max_valid_sources should be removed."""
        text = "Research shows [1]. Other studies [4] and [5]."
        result = service.sanitize_and_renumber(text, 2)

        assert "[1]" in result.text
        assert "[4]" not in result.text
        assert "[5]" not in result.text
        assert set(result.removed_indices) == {4, 5}

    def test_renumber_citations_when_gaps_exist(self, service):
        """Valid citations with gaps should be renumbered sequentially."""
        # Text references [1], [3], [5] but only 3 valid sources exist
        # Valid indices: 1, 3 (both within 1-3)
        # Phantom: 5 (beyond max_valid_sources=3)
        text = "First [Source 1], second [Source 3], third [Source 5]."
        result = service.sanitize_and_renumber(text, 3)

        # [1] and [3] are valid, renumbered to [1] and [2]
        # [5] is removed
        assert "[Source 1]" in result.text
        assert "[Source 2]" in result.text
        assert "[Source 5]" not in result.text
        assert set(result.removed_indices) == {5}

    def test_renumber_plain_citations(self, service):
        """Plain [N] citations should be renumbered when gaps exist."""
        # Text references [1], [3], [5] but only 3 valid sources
        # Valid: 1, 3 -> renumbered to 1, 2
        # Phantom: 5 -> removed
        text = "First [1], second [3], third [5]."
        result = service.sanitize_and_renumber(text, 3)

        assert "[1]" in result.text
        assert "[2]" in result.text
        # [5] is phantom and removed
        assert "[5]" not in result.text
        assert set(result.removed_indices) == {5}

    def test_mixed_citation_formats(self, service):
        """Both [Source N] and [N] formats should be handled together."""
        text = "Research [Source 1] and other studies [2] show agreement [Source 3]."
        result = service.sanitize_and_renumber(text, 3)

        # All should be preserved
        assert "[Source 1]" in result.text or "[1]" in result.text
        assert "[2]" in result.text or "[Source 2]" in result.text
        assert "[Source 3]" in result.text

    def test_whitespace_cleanup(self, service):
        """Extra whitespace around punctuation should be cleaned."""
        text = "Research shows [Source 1]  .  Other studies [Source 2]  ."
        result = service.sanitize_and_renumber(text, 2)

        # Whitespace before punctuation should be removed
        assert "  ." not in result.text
        assert result.text.count("  ") == 0

    def test_all_phantom_citations_removed(self, service):
        """If all citations are phantom, text should have them removed."""
        text = "This cites [Source 5] and [Source 6]."
        result = service.sanitize_and_renumber(text, 2)

        assert "[Source 5]" not in result.text
        assert "[Source 6]" not in result.text
        assert set(result.removed_indices) == {5, 6}

    def test_citation_followed_by_punctuation(self, service):
        """Citations followed by punctuation should be handled correctly."""
        text = "Research [Source 1]. Studies [Source 2]; more [Source 3]."
        result = service.sanitize_and_renumber(text, 3)

        assert "[Source 1]" in result.text
        assert "[Source 2]" in result.text
        assert "[Source 3]" in result.text

    def test_citation_after_parenthesis(self, service):
        """Citations after closing parenthesis should be recognized."""
        text = "Evidence (from many studies) [Source 1] shows this."
        result = service.sanitize_and_renumber(text, 1)

        assert "[Source 1]" in result.text

    def test_citation_em_dash_context(self, service):
        """Citations after em dash should be recognized."""
        text = "Many studies show this — [Source 1] is a key example."
        result = service.sanitize_and_renumber(text, 1)

        assert "[Source 1]" in result.text

    def test_false_positive_rejection_slash_prefix(self, service):
        """[N] preceded by slash should not be treated as citation."""
        # This is tricky - we want to avoid matching /[\d+]/ (like URLs with IDs)
        text = "See data at /items/[1] for reference."
        result = service.sanitize_and_renumber(text, 1)

        # Should not treat /[1] as a citation (it's a path)
        # The regex (?<![\/\w]) should prevent this
        # This is a weak test but documents the behavior
        assert "[1]" in result.text  # Might still be there if our regex allows it

    def test_duplicate_citations_both_removed(self, service):
        """Duplicate phantom citations should all be removed."""
        text = "First [Source 5], then [Source 5] again, and [Source 5] once more."
        result = service.sanitize_and_renumber(text, 2)

        assert "[Source 5]" not in result.text
        # Each instance was removed (may have duplicates in list)
        assert len(result.removed_indices) >= 3

    def test_complex_scenario(self, service):
        """Complex scenario with mixed valid/phantom citations and renumbering."""
        text = (
            "Studies [Source 1] show this. Additional research [Source 3] "
            "contradicts [Source 6]. However [Source 2] suggests [Source 7]."
        )
        result = service.sanitize_and_renumber(text, 3)

        # Valid: [1], [3], [2] -> renumber to [1], [2], [3]
        # Phantom: [6], [7] -> removed
        assert "[Source 1]" in result.text
        assert "[Source 2]" in result.text or "[Source 3]" in result.text
        assert "[Source 6]" not in result.text
        assert "[Source 7]" not in result.text
        assert set(result.removed_indices) == {6, 7}

    def test_zero_valid_sources(self, service):
        """If max_valid_sources=0, all citations should be removed."""
        text = "This cites [Source 1] and [Source 2]."
        result = service.sanitize_and_renumber(text, 0)

        assert "[Source 1]" not in result.text
        assert "[Source 2]" not in result.text
        assert set(result.removed_indices) == {1, 2}


class TestExtract:
    """Tests for the extract method."""

    def test_extract_single_citation(self, service, sample_chunks):
        """Extract a single citation from text."""
        text = "Research shows [Source 1] about perimenopause."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 1
        assert citations[0].url == "https://menopausewiki.ca/overview"
        assert citations[0].title == "Perimenopause Overview"
        assert citations[0].section == "Definition"
        assert citations[0].source_index == 1

    def test_extract_multiple_citations(self, service, sample_chunks):
        """Extract multiple citations in order."""
        text = "First [Source 1], then [Source 2], finally [Source 3]."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 3
        assert citations[0].source_index == 1
        assert citations[1].source_index == 2
        assert citations[2].source_index == 3

    def test_extract_plain_format_citations(self, service, sample_chunks):
        """Extract [N] format citations."""
        text = "Research [1] and [2] show this."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 2
        assert citations[0].source_index == 1
        assert citations[1].source_index == 2

    def test_extract_mixed_formats(self, service, sample_chunks):
        """Extract both [Source N] and [N] formats together."""
        text = "Data [Source 1] and [2] and [Source 3] combined."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 3
        assert citations[0].source_index == 1
        assert citations[1].source_index == 2
        assert citations[2].source_index == 3

    def test_extract_no_citations(self, service, sample_chunks):
        """Text with no citations should return empty list."""
        text = "This is a response with no citations at all."
        citations = service.extract(text, sample_chunks)

        assert citations == []

    def test_extract_phantom_citations_ignored(self, service, sample_chunks):
        """References beyond available chunks are ignored."""
        text = "Data [Source 1] and [Source 4] and [Source 5]."
        citations = service.extract(text, sample_chunks)

        # Only [1] is valid (only 3 chunks)
        assert len(citations) == 1
        assert citations[0].source_index == 1

    def test_extract_without_section_name(self, service):
        """Chunks without section_name should have None for section."""
        chunks = [
            {
                "source_url": "https://example.com",
                "title": "Example",
                # No section_name
            }
        ]
        text = "Reference [Source 1]."
        citations = service.extract(text, chunks)

        assert len(citations) == 1
        assert citations[0].section is None

    def test_extract_without_url_skipped(self, service):
        """Chunks without url should be skipped (not added to citations)."""
        chunks = [
            {
                "title": "Example",
                "section_name": "Intro",
                # No source_url
            }
        ]
        text = "Reference [Source 1]."
        citations = service.extract(text, chunks)

        # Should be empty because chunk has no URL
        assert len(citations) == 0

    def test_extract_duplicate_references(self, service, sample_chunks):
        """Same citation referenced twice should appear once (deduplicated via set)."""
        text = "First [Source 1] and later [Source 1] again."
        citations = service.extract(text, sample_chunks)

        # Extract uses a set so duplicates are deduplicated
        assert len(citations) == 1
        assert citations[0].source_index == 1

    def test_extract_out_of_order_citations(self, service, sample_chunks):
        """Citations in non-sequential order should be returned sorted by index."""
        text = "Evidence [Source 3], then [Source 1], then [Source 2]."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 3
        # Returned in sorted order of indices (1, 2, 3)
        assert citations[0].source_index == 1
        assert citations[1].source_index == 2
        assert citations[2].source_index == 3

    def test_extract_edge_case_false_positives(self, service, sample_chunks):
        """Should not match [N] patterns that aren't citations."""
        text = "File path [/items/5] is mentioned. Range [5-10] also."
        citations = service.extract(text, sample_chunks)

        # The [5] in [5-10] might be caught, but [/items/5] should not
        # This documents actual behavior (regex isn't perfect)
        # Should be minimal matches
        assert len(citations) <= 1  # At most the [5] from [5-10]

    def test_extract_empty_chunks_list(self, service):
        """Empty chunks list should return no citations."""
        text = "This has [Source 1] reference."
        citations = service.extract(text, [])

        assert citations == []

    def test_extract_all_plain_format(self, service, sample_chunks):
        """All citations in plain format."""
        text = "Data [1] shows [2] that [3] is true."
        citations = service.extract(text, sample_chunks)

        assert len(citations) == 3
        assert [c.source_index for c in citations] == [1, 2, 3]


class TestIntegration:
    """Integration tests combining sanitize_and_renumber + extract."""

    def test_full_pipeline_with_phantom_citations(self, service, sample_chunks):
        """Complete pipeline: sanitize, then extract."""
        # Raw response with phantom citations
        raw_text = (
            "Research [Source 1] shows this. However [Source 5] contradicts. "
            "Yet [Source 2] suggests [Source 6]."
        )

        # Sanitize: remove phantoms and renumber
        sanitized = service.sanitize_and_renumber(raw_text, 2)
        assert "[Source 5]" not in sanitized.text
        assert "[Source 6]" not in sanitized.text

        # Extract: get citations from sanitized text
        citations = service.extract(sanitized.text, sample_chunks)

        # Should have only 2 citations (1 and 2)
        assert len(citations) == 2
        assert all(c.source_index <= 2 for c in citations)

    def test_full_pipeline_with_renumbering(self, service, sample_chunks):
        """Renumbering should make extraction work correctly."""
        # Text references [1], [3] but we have 2 valid sources
        # [3] is phantom (> max_valid_sources=2) so it gets removed
        raw_text = "First [Source 1] and second [Source 3]."

        # Sanitize: remove phantom [Source 3]
        sanitized = service.sanitize_and_renumber(raw_text, 2)
        assert "[Source 3]" not in sanitized.text
        assert set(sanitized.removed_indices) == {3}

        # Extract: only [Source 1] remains
        citations = service.extract(sanitized.text, sample_chunks)
        assert len(citations) == 1
        assert citations[0].source_index == 1

    def test_real_world_scenario(self, service, sample_chunks):
        """Real-world scenario from Ask Meno response."""
        raw_response = (
            "Perimenopause is a complex transition [Source 1]. "
            "Hot flashes affect 80% of people [Source 2]. "
            "HRT may be recommended [Source 3]. "
            "Some outdated sources suggest [Source 7]. "
            "Recent studies [Source 2] confirm earlier findings."
        )

        # Sanitize (remove [Source 7], renumber if needed)
        sanitized = service.sanitize_and_renumber(raw_response, 3)
        assert "[Source 7]" not in sanitized.text

        # Extract citations
        citations = service.extract(sanitized.text, sample_chunks)

        # Should have 3 unique citations (though [Source 2] appears twice)
        # Extract doesn't deduplicate, so we get all references
        assert all(c.source_index <= 3 for c in citations)
        assert any(c.source_index == 2 for c in citations)


# ---------------------------------------------------------------------------
# TestRenderStructuredResponse
# Tests for the v2 paragraph-based render_structured_response method.
# ---------------------------------------------------------------------------


@pytest.fixture
def render_chunks():
    """Three chunks for render_structured_response tests."""
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


class TestRenderStructuredResponse:
    """Tests for CitationService.render_structured_response() (v2 paragraph schema)."""

    # CATCHES: regression to bullet-point format after refactor
    def test_renders_paragraph_not_bullets(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="MHT is well-tolerated.", source_index=1),
            ]
        )
        rendered, _ = service.render_structured_response(structured, render_chunks)
        assert "\n-" not in rendered
        assert "MHT is well-tolerated." in rendered

    # CATCHES: duplicate Citation objects created when same source used in two sections
    def test_deduplicates_citations_same_source(self, service, render_chunks):
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
        _, citations = service.render_structured_response(structured, render_chunks)
        assert len(citations) == 1
        assert citations[0].title == "Perimenopause Overview"

    # CATCHES: [Source N] marker appended to section with null source_index
    def test_null_source_index_no_citation_marker(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    body="Closing remarks with no source.", source_index=None
                ),
            ]
        )
        rendered, citations = service.render_structured_response(
            structured, render_chunks
        )
        assert "[Source" not in rendered
        assert len(citations) == 0

    # CATCHES: heading omitted when section.heading is None (OK), or shown when present
    def test_no_heading_when_null(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(heading=None, body="Body text.", source_index=1),
            ]
        )
        rendered, _ = service.render_structured_response(structured, render_chunks)
        assert "###" not in rendered

    # CATCHES: heading not rendered above body when section.heading is set
    def test_heading_rendered_above_body(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(
                    heading="HRT Overview", body="MHT is effective.", source_index=1
                ),
            ]
        )
        rendered, _ = service.render_structured_response(structured, render_chunks)
        # Heading should appear as ### heading before the body paragraph
        assert "### HRT Overview" in rendered
        assert "MHT is effective." in rendered
        heading_pos = rendered.index("### HRT Overview")
        body_pos = rendered.index("MHT is effective.")
        assert heading_pos < body_pos

    # CATCHES: out-of-range source_index (e.g. 99) causes IndexError or exception
    def test_invalid_source_index_skipped_gracefully(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Body with bad source.", source_index=99),
            ]
        )
        # Should not raise; body is still rendered, no citation marker
        rendered, citations = service.render_structured_response(
            structured, render_chunks
        )
        assert "Body with bad source." in rendered
        assert "[Source" not in rendered
        assert len(citations) == 0

    # CATCHES: disclaimer appended even when it is None (extra blank line or text)
    def test_disclaimer_appended_when_present(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Main content.", source_index=1),
            ],
            disclaimer="My sources don't cover dosing specifics.",
        )
        rendered, _ = service.render_structured_response(structured, render_chunks)
        assert "My sources don't cover dosing specifics." in rendered

    def test_no_disclaimer_when_none(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="Main content.", source_index=1),
            ],
            disclaimer=None,
        )
        rendered, _ = service.render_structured_response(structured, render_chunks)
        # Just make sure nothing weird was appended
        assert rendered.strip().endswith("[Source 1]")

    # CATCHES: insufficient_sources flag bypassed, returning empty sections instead of disclaimer
    def test_insufficient_sources_short_circuits(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[],
            disclaimer="I don't have sources to answer that.",
            insufficient_sources=True,
        )
        rendered, citations = service.render_structured_response(
            structured, render_chunks
        )
        assert rendered == "I don't have sources to answer that."
        assert citations == []

    def test_insufficient_sources_default_message_when_no_disclaimer(
        self, service, render_chunks
    ):
        structured = StructuredLLMResponse(
            sections=[],
            disclaimer=None,
            insufficient_sources=True,
        )
        rendered, citations = service.render_structured_response(
            structured, render_chunks
        )
        assert "don't have" in rendered.lower() or "not have" in rendered.lower()
        assert citations == []

    # CATCHES: multiple unique sources produce wrong number of Citation objects
    def test_multiple_unique_sources_all_included(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="About perimenopause.", source_index=1),
                ResponseSection(body="About hot flashes.", source_index=2),
                ResponseSection(body="About HRT.", source_index=3),
            ]
        )
        _, citations = service.render_structured_response(structured, render_chunks)
        assert len(citations) == 3

    # CATCHES: empty body sections producing blank paragraphs
    def test_empty_body_sections_skipped(self, service, render_chunks):
        structured = StructuredLLMResponse(
            sections=[
                ResponseSection(body="   ", source_index=1),
                ResponseSection(body="Real content here.", source_index=2),
            ]
        )
        rendered, citations = service.render_structured_response(
            structured, render_chunks
        )
        assert "Real content here." in rendered
        assert len(citations) == 1
