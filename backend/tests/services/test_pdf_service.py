"""Tests for PdfService."""

from datetime import date

import pytest

from app.models.appointment import CheatsheetResponse, ProviderSummaryResponse, QuestionGroup
from app.models.symptoms import SymptomFrequency, SymptomPair
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

        return SymptomFrequency(
            symptom_id="sym-1", symptom_name=name, category=category, count=count
        )

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


# ---------------------------------------------------------------------------
# build_provider_summary_pdf (Phase 4)
# ---------------------------------------------------------------------------


def _freq(name, cat, count):
    return SymptomFrequency(symptom_id="s1", symptom_name=name, category=cat, count=count)


def _pair(s1, s2, count, rate):
    return SymptomPair(
        symptom1_id="s1", symptom1_name=s1,
        symptom2_id="s2", symptom2_name=s2,
        cooccurrence_count=count, cooccurrence_rate=rate,
        total_occurrences_symptom1=count + 2,
    )


def _provider_content(**overrides):
    defaults = dict(
        opening="Patient is 52 presenting with hot flashes.",
        symptom_picture="Logs show 12 hot flash episodes.",
        key_patterns="Hot flashes co-occur with night sweats.",
        closing="Patient seeks discussion of treatment options.",
    )
    return ProviderSummaryResponse(**{**defaults, **overrides})


def _cheatsheet_content(**overrides):
    defaults = dict(
        opening_statement="I am 52 in late perimenopause.",
        question_groups=[
            QuestionGroup(topic="Hot flashes", questions=["Could you help me understand..."])
        ],
    )
    return CheatsheetResponse(**{**defaults, **overrides})


class TestBuildProviderSummaryPdf:
    def test_returns_bytes(self, svc):
        # CATCHES: method not implemented — appointment Step 5 would crash calling
        # a method that doesn't exist on PdfService
        result = svc.build_provider_summary_pdf(
            content=_provider_content(),
            frequency_stats=[],
            cooccurrence_stats=[],
            concerns=["Understand options"],
        )
        assert isinstance(result, bytes)

    def test_starts_with_pdf_magic_bytes(self, svc):
        # CATCHES: reportlab build fails silently — bytes returned but not a valid
        # PDF, causing Supabase upload to produce a corrupt file
        result = svc.build_provider_summary_pdf(
            content=_provider_content(),
            frequency_stats=[],
            cooccurrence_stats=[],
            concerns=[],
        )
        assert result[:4] == b"%PDF"

    def test_renders_with_frequency_table(self, svc):
        # CATCHES: frequency_stats parameter ignored — provider summary PDF would
        # have no symptom data table, making it useless for the provider
        result = svc.build_provider_summary_pdf(
            content=_provider_content(),
            frequency_stats=[_freq("Hot flashes", "vasomotor", 15)],
            cooccurrence_stats=[],
            concerns=["Discuss treatment"],
        )
        assert result[:4] == b"%PDF"

    def test_renders_with_cooccurrence_table(self, svc):
        # CATCHES: cooccurrence_stats parameter ignored — co-occurrence table absent
        # from provider summary, losing a key clinical pattern indicator
        result = svc.build_provider_summary_pdf(
            content=_provider_content(),
            frequency_stats=[_freq("Hot flashes", "vasomotor", 12)],
            cooccurrence_stats=[_pair("Hot flashes", "Night sweats", 8, 0.8)],
            concerns=["Discuss HRT"],
        )
        assert result[:4] == b"%PDF"

    def test_renders_with_empty_key_patterns(self, svc):
        # CATCHES: empty key_patterns crashes the PDF builder — LLM sometimes
        # omits this section when no clear patterns exist
        result = svc.build_provider_summary_pdf(
            content=_provider_content(key_patterns=""),
            frequency_stats=[],
            cooccurrence_stats=[],
            concerns=[],
        )
        assert result[:4] == b"%PDF"

    def test_no_user_name_in_content(self, svc):
        # CATCHES: user name interpolated into PDF — privacy requirement that no
        # personal identifiers appear in generated PDFs
        content = _provider_content(
            opening="The patient is presenting today.",
            symptom_picture="Logs show symptoms.",
            closing="Seeking discussion.",
        )
        result = svc.build_provider_summary_pdf(
            content=content,
            frequency_stats=[],
            cooccurrence_stats=[],
            concerns=[],
        )
        # PDF bytes don't contain literal user-identifying strings passed from service
        assert b"Sarah Smith" not in result
        assert b"user-456" not in result


class TestBuildCheatsheetPdf:
    def test_returns_bytes(self, svc):
        # CATCHES: method not implemented — appointment Step 5 would crash on
        # build_cheatsheet_pdf which doesn't exist on PdfService yet
        result = svc.build_cheatsheet_pdf(
            content=_cheatsheet_content(),
            concerns=["Understand options"],
            scenarios=[],
            frequency_stats=[],
        )
        assert isinstance(result, bytes)

    def test_starts_with_pdf_magic_bytes(self, svc):
        # CATCHES: reportlab build error returns empty bytes — cheatsheet upload
        # would store a corrupt file the user cannot open
        result = svc.build_cheatsheet_pdf(
            content=_cheatsheet_content(),
            concerns=[],
            scenarios=[],
            frequency_stats=[],
        )
        assert result[:4] == b"%PDF"

    def test_renders_with_scenarios(self, svc):
        # CATCHES: scenarios parameter ignored — "If Things Go Sideways" section
        # would be missing even when Step 4 produced scenario cards
        scenarios = [
            {"title": "Let's try lifestyle changes first", "suggestion": "I hear you, but..."}
        ]
        result = svc.build_cheatsheet_pdf(
            content=_cheatsheet_content(),
            concerns=["Discuss HRT"],
            scenarios=scenarios,
            frequency_stats=[],
        )
        assert result[:4] == b"%PDF"

    def test_renders_with_frequency_stats(self, svc):
        # CATCHES: frequency_stats ignored — symptoms ranked by impact section
        # would be empty, removing the key talking-point summary
        result = svc.build_cheatsheet_pdf(
            content=_cheatsheet_content(),
            concerns=["Get a plan"],
            scenarios=[],
            frequency_stats=[_freq("Hot flashes", "vasomotor", 12)],
        )
        assert result[:4] == b"%PDF"

    def test_renders_empty_scenarios(self, svc):
        # CATCHES: scenarios=[] crashes the PDF builder — appointment prep is valid
        # without going through Step 4 (user skips scenario practice)
        result = svc.build_cheatsheet_pdf(
            content=_cheatsheet_content(),
            concerns=["Ask about HRT"],
            scenarios=[],
            frequency_stats=[],
        )
        assert result[:4] == b"%PDF"
