"""Tests for prompt_formatting utility functions.

These functions format symptom stats into LLM prompt text. The tests focus
on behavior: correct format variants, sentinel strings, and caps — all of
which are asserted on by the three call sites that use these utilities.
"""

from datetime import date
from unittest.mock import MagicMock

from app.models.medications import MedicationResponse
from app.models.symptoms import SymptomFrequency, SymptomPair
from app.utils.prompt_formatting import (
    format_cooccurrence_stats_for_prompt,
    format_frequency_stats_for_prompt,
    format_medications_for_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_freq(name: str, category: str, count: int) -> SymptomFrequency:
    return SymptomFrequency(
        symptom_id="id-1",
        symptom_name=name,
        category=category,
        count=count,
    )


def make_pair(
    name1: str, name2: str, count: int, rate: float
) -> SymptomPair:
    return SymptomPair(
        symptom1_id="id-1",
        symptom1_name=name1,
        symptom2_id="id-2",
        symptom2_name=name2,
        cooccurrence_count=count,
        cooccurrence_rate=rate,
        total_occurrences_symptom1=count * 2,
    )


def make_med(
    name: str,
    dose: str,
    delivery: str = "pill",
    start: date = date(2026, 1, 1),
) -> MedicationResponse:
    return MedicationResponse(
        id="med-1",
        medication_name=name,
        dose=dose,
        delivery_method=delivery,  # type: ignore[arg-type]
        start_date=start,
    )


# ---------------------------------------------------------------------------
# format_frequency_stats_for_prompt
# ---------------------------------------------------------------------------


class TestFormatFrequencyStatsForPrompt:
    def test_empty_returns_default_sentinel(self):
        # CATCHES: returning empty string on empty input — the LLM would receive
        # a blank section header with no content, producing hallucinated data
        result = format_frequency_stats_for_prompt([])
        assert result == "No symptom data available."

    def test_empty_custom_sentinel(self):
        # CATCHES: ignoring the empty_msg parameter and always returning the
        # default sentinel — generate_provider_questions would get the wrong
        # sentinel string, breaking its prompt structure
        result = format_frequency_stats_for_prompt([], empty_msg="No symptom data.")
        assert result == "No symptom data."

    def test_includes_category_by_default(self):
        # CATCHES: stripping the category field — appointment.py and
        # generate_symptom_summary both need "(category)" for clinical context
        stats = [make_freq("Hot flashes", "vasomotor", 12)]
        result = format_frequency_stats_for_prompt(stats)
        assert "Hot flashes (vasomotor): logged 12 time(s)" in result

    def test_omits_category_when_include_category_false(self):
        # CATCHES: ignoring the include_category flag — generate_provider_questions
        # would produce a different format than its existing prompt expected
        stats = [make_freq("Hot flashes", "vasomotor", 12)]
        result = format_frequency_stats_for_prompt(stats, include_category=False)
        assert "Hot flashes: logged 12 time(s)" in result
        assert "(vasomotor)" not in result

    def test_multiple_symptoms_one_per_line(self):
        # CATCHES: joining with spaces instead of newlines — the LLM would see
        # all symptoms as one run-on line and miss individual entries
        stats = [
            make_freq("Hot flashes", "vasomotor", 12),
            make_freq("Brain fog", "cognitive", 8),
        ]
        result = format_frequency_stats_for_prompt(stats)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("- Hot flashes")
        assert lines[1].startswith("- Brain fog")

    def test_max_items_caps_output(self):
        # CATCHES: off-by-one in slice — passing 11 items when max_items=10
        # would silently exceed the intended prompt length budget
        stats = [make_freq(f"Symptom {i}", "cat", i) for i in range(15)]
        result = format_frequency_stats_for_prompt(stats, max_items=5)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 5

    def test_default_max_is_ten(self):
        # CATCHES: default max being too large — prompts should not grow
        # unboundedly if the user has logged 50 different symptoms
        stats = [make_freq(f"Symptom {i}", "cat", i) for i in range(12)]
        result = format_frequency_stats_for_prompt(stats)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 10

    def test_each_line_starts_with_dash(self):
        # CATCHES: missing the "- " prefix — the LLM prompt relies on
        # bullet formatting to parse the list structure
        stats = [make_freq("Brain fog", "cognitive", 5)]
        result = format_frequency_stats_for_prompt(stats)
        assert result.startswith("- ")

    def test_generate_symptom_summary_sentinel_preserved(self):
        # CATCHES: changing the sentinel wording — test_llm.py asserts
        # "No symptom data available" appears in the assembled user_prompt
        result = format_frequency_stats_for_prompt([])
        assert "No symptom data available" in result

    def test_provider_questions_sentinel_preserved(self):
        # CATCHES: default sentinel leaking into provider-questions path —
        # "available." appears in a prompt that was designed without it
        result = format_frequency_stats_for_prompt([], empty_msg="No symptom data.")
        assert result == "No symptom data."


# ---------------------------------------------------------------------------
# format_cooccurrence_stats_for_prompt
# ---------------------------------------------------------------------------


class TestFormatCooccurrenceStatsForPrompt:
    def test_empty_returns_sentinel(self):
        # CATCHES: returning "" on empty input — the LLM would see a blank
        # co-occurrence section and either hallucinate patterns or error
        result = format_cooccurrence_stats_for_prompt([])
        assert result == "No notable co-occurrence patterns."

    def test_verbose_includes_percentage(self):
        # CATCHES: omitting the rate in verbose mode — the provider summary
        # prompt depends on "X% of Y logs" to convey clinical significance
        pairs = [make_pair("Hot flashes", "Night sweats", 8, 0.75)]
        result = format_cooccurrence_stats_for_prompt(pairs, verbose=True)
        assert "75%" in result
        assert "Hot flashes + Night sweats" in result

    def test_verbose_uses_plus_separator(self):
        # CATCHES: using "and" separator in verbose mode — narrative and export
        # prompts expect "+" to distinguish them from the compact format
        pairs = [make_pair("Sleep issues", "Brain fog", 5, 0.5)]
        result = format_cooccurrence_stats_for_prompt(pairs, verbose=True)
        assert "Sleep issues + Brain fog" in result

    def test_compact_uses_and_separator(self):
        # CATCHES: using "+" in compact mode — generate_provider_questions uses
        # "and" to make questions read naturally in first-person speech
        pairs = [make_pair("Sleep issues", "Brain fog", 5, 0.5)]
        result = format_cooccurrence_stats_for_prompt(pairs, verbose=False)
        assert "Sleep issues and Brain fog" in result
        assert "+" not in result

    def test_compact_omits_percentage(self):
        # CATCHES: including the rate in compact mode — the provider-questions
        # prompt expects the shorter format without statistical annotation
        pairs = [make_pair("Hot flashes", "Night sweats", 8, 0.75)]
        result = format_cooccurrence_stats_for_prompt(pairs, verbose=False)
        assert "75%" not in result
        assert "co-occurred 8 time(s)" in result

    def test_default_is_verbose(self):
        # CATCHES: defaulting to compact — narrative and export prompts
        # (the common case) need the percentage rate by default
        pairs = [make_pair("Hot flashes", "Night sweats", 8, 0.75)]
        result = format_cooccurrence_stats_for_prompt(pairs)
        assert "%" in result

    def test_max_items_caps_output(self):
        # CATCHES: ignoring max_items and returning all pairs — prompts would
        # grow beyond token budgets if many co-occurring pairs are present
        pairs = [make_pair(f"S{i}", f"S{i+1}", i + 1, 0.5) for i in range(8)]
        result = format_cooccurrence_stats_for_prompt(pairs, max_items=3)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 3

    def test_default_max_is_five(self):
        # CATCHES: default cap being too large — prevents prompt bloat when
        # logs contain many symptom pairs
        pairs = [make_pair(f"S{i}", f"S{i+1}", i + 1, 0.5) for i in range(8)]
        result = format_cooccurrence_stats_for_prompt(pairs)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 5

    def test_each_line_starts_with_dash(self):
        # CATCHES: missing bullet formatting — LLM prompts depend on "- " prefix
        # to parse list structure
        pairs = [make_pair("A", "B", 3, 0.3)]
        result = format_cooccurrence_stats_for_prompt(pairs)
        assert result.startswith("- ")

    def test_percentage_rounded_correctly(self):
        # CATCHES: using raw float (e.g. "66.6%") instead of rounded integer —
        # fractional percentages look noisy and unprofessional in clinical prompts
        pairs = [make_pair("A", "B", 5, 0.666)]
        result = format_cooccurrence_stats_for_prompt(pairs, verbose=True)
        assert "67%" in result


# ---------------------------------------------------------------------------
# format_medications_for_prompt
# ---------------------------------------------------------------------------


class TestFormatMedicationsForPrompt:
    def test_empty_list_returns_empty_string(self):
        # CATCHES: returning the header "Current MHT medications:\n" with no
        # entries — the LLM would see an empty section and hallucinate meds
        result = format_medications_for_prompt([])
        assert result == ""

    def test_includes_medication_name_dose_and_delivery(self):
        # CATCHES: omitting dose or delivery method — the clinical narrative
        # needs all three to give the provider complete treatment context
        meds = [make_med("Estradiol", "1mg")]
        result = format_medications_for_prompt(meds)
        assert "Estradiol 1mg (pill)" in result

    def test_includes_start_date_when_present(self):
        # CATCHES: silently dropping start_date — the provider needs to know
        # how long the patient has been on a medication
        meds = [make_med("Estradiol", "1mg", start=date(2025, 6, 1))]
        result = format_medications_for_prompt(meds)
        assert "started 2025-06-01" in result

    def test_no_start_date_text_when_none(self):
        # CATCHES: crashing on None start_date, or printing "started None" —
        # start_date is optional and omitting it should produce clean output
        mock_med = MagicMock()
        mock_med.medication_name = "Progesterone"
        mock_med.dose = "200mg"
        mock_med.delivery_method = "oral"
        mock_med.start_date = None
        result = format_medications_for_prompt([mock_med])  # type: ignore[list-item]
        assert "started" not in result
        assert "Progesterone 200mg (oral)" in result

    def test_leading_double_newline_and_header(self):
        # CATCHES: missing the "\n\n" prefix — the medication section must be
        # visually separated from the preceding prompt content
        meds = [make_med("Estradiol", "1mg")]
        result = format_medications_for_prompt(meds)
        assert result.startswith("\n\nCurrent MHT medications:\n")

    def test_multiple_medications_each_on_own_line(self):
        # CATCHES: joining meds with spaces or commas — each medication must
        # appear on its own "- " line for the LLM to parse them individually
        meds = [
            make_med("Estradiol", "1mg"),
            make_med("Progesterone", "200mg"),
        ]
        result = format_medications_for_prompt(meds)
        lines = [line for line in result.split("\n") if line.strip().startswith("-")]
        assert len(lines) == 2
