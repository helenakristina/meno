"""Tests for appointment prompt constants and builder functions.

Each system prompt constant is tested for:
- Non-empty string (import itself proves the module exists)
- Guardrail strings required by the medical-advice boundary

Each builder function is tested for:
- Dynamic values appear in output
- Return type is str
"""

from datetime import date

from app.llm.appointment_prompts import (
    CHEATSHEET_SYSTEM,
    NARRATIVE_SYSTEM,
    PROVIDER_QUESTIONS_SYSTEM,
    PROVIDER_SUMMARY_SYSTEM,
    SCENARIO_SUGGESTIONS_SYSTEM,
    SYMPTOM_SUMMARY_SYSTEM,
    build_cheatsheet_user_prompt,
    build_narrative_user_prompt,
    build_provider_questions_user_prompt,
    build_provider_summary_user_prompt,
    build_scenario_suggestions_user_prompt,
    build_symptom_summary_user_prompt,
)


# ---------------------------------------------------------------------------
# System prompt constants — guardrails
# ---------------------------------------------------------------------------


class TestNarrativeSystem:
    def test_is_non_empty_string(self):
        # CATCHES: module exists but constant is empty or None — prompt would
        # send a blank system instruction and LLM would have no guardrails
        assert isinstance(NARRATIVE_SYSTEM, str) and NARRATIVE_SYSTEM.strip()

    def test_contains_logs_show_rule(self):
        # CATCHES: clinical language rule removed — LLM would produce "you have"
        # or "you are experiencing" phrasing instead of objective "logs show"
        assert "logs show" in NARRATIVE_SYSTEM.lower()

    def test_contains_no_diagnosis_guardrail(self):
        # CATCHES: diagnosis guardrail stripped — LLM could produce diagnostic
        # statements that cross Meno's medical-advice boundary
        assert "diagnos" in NARRATIVE_SYSTEM.lower()

    def test_contains_discuss_with_provider(self):
        # CATCHES: provider-discussion closing instruction removed — LLM would not
        # end summaries with the required "discuss with a provider" framing
        assert "discuss" in NARRATIVE_SYSTEM.lower() and "provider" in NARRATIVE_SYSTEM.lower()


class TestSymptomSummarySystem:
    def test_is_non_empty_string(self):
        # CATCHES: constant missing — generate_symptom_summary would call LLM
        # with an empty system prompt
        assert isinstance(SYMPTOM_SUMMARY_SYSTEM, str) and SYMPTOM_SUMMARY_SYSTEM.strip()

    def test_contains_logs_show_rule(self):
        # CATCHES: "logs show" rule absent — symptom summary would use "you have"
        # phrasing, violating the clinical objectivity requirement
        assert "logs show" in SYMPTOM_SUMMARY_SYSTEM.lower()

    def test_contains_no_diagnosis_guardrail(self):
        # CATCHES: diagnosis rule absent — LLM could name conditions like
        # "you have perimenopause" in a provider-facing document
        assert "diagnos" in SYMPTOM_SUMMARY_SYSTEM.lower()

    def test_contains_discuss_with_provider(self):
        # CATCHES: closing instruction absent — summary would not direct patterns
        # toward provider discussion, breaking the clinical summary structure
        assert "provider" in SYMPTOM_SUMMARY_SYSTEM.lower()


class TestProviderQuestionsSystem:
    def test_is_non_empty_string(self):
        # CATCHES: constant empty — question generation would have no guardrails
        # and could produce treatment requests or diagnostic questions
        assert isinstance(PROVIDER_QUESTIONS_SYSTEM, str) and PROVIDER_QUESTIONS_SYSTEM.strip()

    def test_contains_no_diagnosis_guardrail(self):
        # CATCHES: diagnosis rule absent — generated questions could ask "Do I
        # have perimenopause?" instead of information-gathering questions
        assert "diagnos" in PROVIDER_QUESTIONS_SYSTEM.lower()

    def test_contains_information_gathering_framing(self):
        # CATCHES: framing instruction removed — questions would lose the
        # "Could you help me understand" voice that makes them appropriate
        assert "understand" in PROVIDER_QUESTIONS_SYSTEM.lower()


class TestScenarioSuggestionsSystem:
    def test_is_non_empty_string(self):
        # CATCHES: constant empty — scenario coaching would be unguided and
        # could produce confrontational or medically unsafe language
        assert isinstance(SCENARIO_SUGGESTIONS_SYSTEM, str) and SCENARIO_SUGGESTIONS_SYSTEM.strip()

    def test_contains_no_diagnosis_guardrail(self):
        # CATCHES: guardrail absent — scenario responses could tell users they
        # have a condition or recommend specific medications
        assert "diagnos" in SCENARIO_SUGGESTIONS_SYSTEM.lower()

    def test_is_patient_facing_not_clinical(self):
        # CATCHES: wrong voice — scenario coaching should sound like a confident
        # friend, not a clinical report; check for first-person coaching language
        assert "she" in SCENARIO_SUGGESTIONS_SYSTEM.lower() or "her" in SCENARIO_SUGGESTIONS_SYSTEM.lower()


class TestProviderSummarySystem:
    def test_is_non_empty_string(self):
        # CATCHES: constant missing — provider summary PDF would be generated
        # without system instructions
        assert isinstance(PROVIDER_SUMMARY_SYSTEM, str) and PROVIDER_SUMMARY_SYSTEM.strip()

    def test_is_separate_from_cheatsheet_system(self):
        # CATCHES: constants share the same string — Phase 2 separates them so
        # provider and patient-facing documents can diverge in voice
        assert PROVIDER_SUMMARY_SYSTEM != CHEATSHEET_SYSTEM


class TestCheatsheetSystem:
    def test_is_non_empty_string(self):
        # CATCHES: constant missing — cheatsheet PDF would be generated without
        # system instructions
        assert isinstance(CHEATSHEET_SYSTEM, str) and CHEATSHEET_SYSTEM.strip()


# ---------------------------------------------------------------------------
# Builder functions — dynamic values
# ---------------------------------------------------------------------------


class TestBuildNarrativeUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            appt_type_str="New Provider",
            goal_str="explore hrt",
            age_str="52",
            journey_stage="perimenopause",
            days_back=60,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            freq_text="- Hot flashes: logged 12 time(s)",
            coocc_text="- Hot flashes + Night sweats: co-occurred 8 time(s)",
            med_section="",
        )
        return build_narrative_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns None or wrong type — appointment.py would
        # pass None as user_prompt to the LLM, raising a TypeError
        assert isinstance(self._call(), str)

    def test_includes_appointment_type(self):
        # CATCHES: appt_type_str not interpolated — provider would see an
        # incomplete context description missing the appointment type
        result = self._call(appt_type_str="Established Relationship")
        assert "Established Relationship" in result

    def test_includes_goal(self):
        # CATCHES: goal_str not interpolated — LLM context would be missing
        # the appointment goal, producing a generic rather than targeted narrative
        result = self._call(goal_str="optimize current treatment")
        assert "optimize current treatment" in result

    def test_includes_age(self):
        # CATCHES: age_str not interpolated — clinical narrative would lack
        # age context that providers need for risk assessment
        result = self._call(age_str="48")
        assert "48" in result

    def test_includes_date_range(self):
        # CATCHES: date formatting removed — provider summary wouldn't show
        # what period the symptom data covers
        result = self._call(start_date=date(2026, 1, 15), end_date=date(2026, 3, 15))
        assert "January" in result or "2026" in result

    def test_includes_freq_text(self):
        # CATCHES: freq_text not interpolated — narrative prompt would have an
        # empty symptom section and LLM would hallucinate symptom data
        result = self._call(freq_text="- Brain fog: logged 10 time(s)")
        assert "Brain fog" in result

    def test_includes_med_section_when_provided(self):
        # CATCHES: med_section not appended — provider would not know the
        # patient's current medications when reading the narrative
        result = self._call(med_section="\n\nCurrent MHT medications:\n- Estradiol 1mg (pill)")
        assert "Estradiol" in result


class TestBuildSymptomSummaryUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            start=date(2026, 1, 1),
            end=date(2026, 3, 1),
            freq_text="- Hot flashes: logged 12 time(s)",
            coocc_text="- Hot flashes + Night sweats: co-occurred 8 time(s)",
        )
        return build_symptom_summary_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns wrong type — generate_symptom_summary would
        # pass invalid user_prompt to LLM provider
        assert isinstance(self._call(), str)

    def test_includes_date_range(self):
        # CATCHES: date range not interpolated — symptom summary would not show
        # what period the data covers, making it useless as a time-anchored report
        result = self._call(start=date(2026, 2, 1), end=date(2026, 3, 31))
        assert "February" in result or "2026" in result

    def test_includes_freq_text(self):
        # CATCHES: freq_text not in output — LLM would generate a summary with
        # no symptom data and produce hallucinated content
        result = self._call(freq_text="- Night sweats: logged 9 time(s)")
        assert "Night sweats" in result


class TestBuildProviderQuestionsUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            freq_text="- Brain fog: logged 8 time(s)",
            coocc_text="- Brain fog and Sleep issues co-occurred 5 time(s)",
            user_context="",
        )
        return build_provider_questions_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns wrong type — generate_provider_questions
        # would crash passing the wrong type to chat_completion
        assert isinstance(self._call(), str)

    def test_includes_freq_text(self):
        # CATCHES: freq_text not interpolated — provider questions would be
        # generated with no symptom context, producing generic useless questions
        result = self._call(freq_text="- Hot flashes: logged 14 time(s)")
        assert "Hot flashes" in result

    def test_includes_user_context_when_provided(self):
        # CATCHES: user_context not appended — questions would miss the journey
        # stage context that tailors them to the user's specific situation
        result = self._call(user_context="Patient is in early perimenopause")
        assert "early perimenopause" in result

    def test_empty_user_context_produces_no_none_string(self):
        # CATCHES: f-string includes "None" or "null" when user_context is empty
        # — LLM would see "Additional context: None" as literal text
        result = self._call(user_context="")
        assert "None" not in result


class TestBuildScenarioSuggestionsUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            scenarios_text="- Hormone therapy increases breast cancer risk",
            concerns_text="- Understand my options\n- Discuss HRT",
            appointment_type="new_provider",
            goal="explore_hrt",
            dismissed_before="once_or_twice",
            age_str="50",
        )
        return build_scenario_suggestions_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns wrong type — generate_scenario_suggestions
        # would crash at the provider.chat_completion call
        assert isinstance(self._call(), str)

    def test_includes_scenarios(self):
        # CATCHES: scenarios_text not interpolated — LLM would generate suggestions
        # for no specific dismissals, producing generic unusable responses
        result = self._call(scenarios_text="- Let's try an antidepressant first")
        assert "antidepressant" in result

    def test_includes_concerns(self):
        # CATCHES: concerns_text not interpolated — generated responses would not
        # be tailored to what the user actually wants from the appointment
        result = self._call(concerns_text="- Get a hormone panel done")
        assert "hormone panel" in result

    def test_includes_age(self):
        # CATCHES: age_str not interpolated — scenario responses would miss age
        # context needed for accurate evidence-based guidance
        result = self._call(age_str="45")
        assert "45" in result


class TestBuildProviderSummaryUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            narrative="Logs show 12 hot flash episodes over 60 days.",
            concerns_text="- Understand options\n- Discuss sleep",
            appointment_type="new_provider",
            goal="explore_hrt",
            age_str="52",
            urgent_symptom=None,
        )
        return build_provider_summary_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns wrong type — generate_pdf_content would
        # pass invalid user_prompt to chat_completion
        assert isinstance(self._call(), str)

    def test_includes_narrative(self):
        # CATCHES: narrative not interpolated — provider summary would not
        # contain the symptom pattern data the provider needs to read
        result = self._call(narrative="Logs show 9 night sweats in 30 days.")
        assert "night sweats" in result

    def test_includes_urgent_symptom_when_provided(self):
        # CATCHES: urgent_symptom not emphasized — the urgent concern that led
        # the user to book the appointment would be buried or absent
        result = self._call(urgent_symptom="severe hot flashes")
        assert "severe hot flashes" in result

    def test_no_urgent_symptom_produces_no_none_string(self):
        # CATCHES: urgent_symptom=None renders as literal "None" in the prompt —
        # provider sees "Urgent Concern: None" rather than a clean omission
        result = self._call(urgent_symptom=None)
        assert "None" not in result

    def test_includes_age(self):
        # CATCHES: age_str not interpolated — provider would not know patient
        # age, missing critical context for perimenopause risk assessment
        result = self._call(age_str="47")
        assert "47" in result


class TestBuildCheatsheetUserPrompt:
    def _call(self, **overrides):
        defaults = dict(
            narrative="Logs show 12 hot flash episodes.",
            concerns_text="- Understand options",
            appointment_type="new_provider",
            goal="explore_hrt",
            age_str="52",
            urgent_symptom=None,
            scenarios=None,
        )
        return build_cheatsheet_user_prompt(**{**defaults, **overrides})

    def test_returns_string(self):
        # CATCHES: function returns wrong type — generate_pdf_content would pass
        # invalid user_prompt to chat_completion
        assert isinstance(self._call(), str)

    def test_includes_narrative(self):
        # CATCHES: narrative not interpolated — cheatsheet would have no symptom
        # context and produce a generic, useless document
        result = self._call(narrative="Logs show 5 brain fog events.")
        assert "brain fog" in result

    def test_includes_urgent_symptom_when_provided(self):
        # CATCHES: urgent_symptom not emphasized — the primary appointment concern
        # would not be highlighted as the first focus in the cheatsheet
        result = self._call(urgent_symptom="joint pain")
        assert "joint pain" in result

    def test_accepts_scenarios_parameter_without_error(self):
        # CATCHES: scenarios parameter rejected by builder signature — cheatsheet
        # prompt call from generate_cheatsheet_content() would raise TypeError
        # Note: scenarios are rendered by the PDF builder, not embedded in the LLM prompt
        scenarios = [{"title": "Let's try lifestyle changes", "suggestion": "I hear you, but..."}]
        result = self._call(scenarios=scenarios)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_no_urgent_symptom_produces_no_none_string(self):
        # CATCHES: urgent_symptom=None renders as "None" — cheatsheet would show
        # "Urgent Concern: None" rather than gracefully omitting it
        result = self._call(urgent_symptom=None)
        assert "None" not in result
