"""Tests for PdfService."""

from datetime import date

import pytest

from app.services.pdf import PdfService


@pytest.fixture
def svc():
    return PdfService()


# ---------------------------------------------------------------------------
# _inline_md
# ---------------------------------------------------------------------------


class TestInlineMd:
    def test_bold(self, svc):
        assert svc._inline_md("**bold**") == "<b>bold</b>"

    def test_italic(self, svc):
        assert svc._inline_md("*italic*") == "<i>italic</i>"

    def test_bold_italic(self, svc):
        assert svc._inline_md("***both***") == "<b><i>both</i></b>"

    def test_inline_code(self, svc):
        assert svc._inline_md("`code`") == '<font face="Courier">code</font>'

    def test_plain_text_unchanged(self, svc):
        assert svc._inline_md("plain text") == "plain text"

    def test_underscore_bold(self, svc):
        assert svc._inline_md("__bold__") == "<b>bold</b>"

    def test_underscore_italic(self, svc):
        assert svc._inline_md("_italic_") == "<i>italic</i>"


# ---------------------------------------------------------------------------
# markdown_to_pdf
# ---------------------------------------------------------------------------


class TestMarkdownToPdf:
    def test_returns_bytes(self, svc):
        result = svc.markdown_to_pdf("Hello world")
        assert isinstance(result, bytes)

    def test_starts_with_pdf_magic(self, svc):
        result = svc.markdown_to_pdf("Hello world")
        assert result[:4] == b"%PDF"

    def test_with_title(self, svc):
        result = svc.markdown_to_pdf("## Section", title="My Title")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_empty_string_returns_pdf(self, svc):
        result = svc.markdown_to_pdf("")
        assert result[:4] == b"%PDF"

    def test_headings(self, svc):
        md = "# H1\n## H2\n### H3\n#### H4"
        result = svc.markdown_to_pdf(md)
        assert isinstance(result, bytes)

    def test_bullet_list(self, svc):
        md = "- item one\n- item two\n* item three"
        result = svc.markdown_to_pdf(md)
        assert isinstance(result, bytes)

    def test_numbered_list(self, svc):
        md = "1. first\n2. second\n3. third"
        result = svc.markdown_to_pdf(md)
        assert isinstance(result, bytes)

    def test_hr_divider(self, svc):
        md = "Before\n---\nAfter"
        result = svc.markdown_to_pdf(md)
        assert isinstance(result, bytes)

    def test_inline_formatting_in_body(self, svc):
        md = "This is **bold** and *italic* and `code`."
        result = svc.markdown_to_pdf(md)
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# build_export_pdf
# ---------------------------------------------------------------------------


class TestBuildExportPdf:
    def _freq_stat(self, name, category, count):
        from app.models.symptoms import SymptomFrequency

        return SymptomFrequency(symptom_id="sym-1", symptom_name=name, category=category, count=count)

    def _coocc_pair(self, s1, s2, count, rate):
        from app.models.symptoms import SymptomPair

        return SymptomPair(
            symptom1_id="sym-1",
            symptom1_name=s1,
            symptom2_id="sym-2",
            symptom2_name=s2,
            cooccurrence_count=count,
            cooccurrence_rate=rate,
            total_occurrences_symptom1=count + 2,
        )

    def test_returns_bytes(self, svc):
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="Summary text.",
            frequency_stats=[],
            cooccurrence_pairs=[],
            provider_questions=[],
        )
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_with_frequency_stats(self, svc):
        stats = [self._freq_stat("Hot flashes", "vasomotor", 15)]
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="Pattern summary.",
            frequency_stats=stats,
            cooccurrence_pairs=[],
            provider_questions=[],
        )
        assert result[:4] == b"%PDF"

    def test_with_cooccurrence_pairs(self, svc):
        pairs = [self._coocc_pair("Hot flashes", "Night sweats", 8, 0.8)]
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="Pattern summary.",
            frequency_stats=[],
            cooccurrence_pairs=pairs,
            provider_questions=[],
        )
        assert result[:4] == b"%PDF"

    def test_with_provider_questions(self, svc):
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="Summary.",
            frequency_stats=[],
            cooccurrence_pairs=[],
            provider_questions=["Ask about HRT", "Discuss sleep aids"],
        )
        assert result[:4] == b"%PDF"

    def test_all_sections_populated(self, svc):
        stats = [
            self._freq_stat("Hot flashes", "vasomotor", 15),
            self._freq_stat("Brain fog", "cognitive", 10),
        ]
        pairs = [self._coocc_pair("Hot flashes", "Night sweats", 5, 0.5)]
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="Hot flashes and night sweats occurred frequently.\n\nBrain fog was also noted.",
            frequency_stats=stats,
            cooccurrence_pairs=pairs,
            provider_questions=["Should I consider HRT?"],
        )
        assert isinstance(result, bytes)
        assert len(result) > 1000

    def test_empty_frequency_table_shows_placeholder(self, svc):
        """No crash when frequency_stats is empty — table shows placeholder row."""
        result = svc.build_export_pdf(
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
            ai_summary="No data.",
            frequency_stats=[],
            cooccurrence_pairs=[],
            provider_questions=[],
        )
        assert result[:4] == b"%PDF"
