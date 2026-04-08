"""Tests for Phase 4 PDF output models.

These models parse LLM JSON responses for structured PDF generation.
extra="ignore" lets unknown fields pass through; missing required fields
must raise ValidationError so the hard-fail path in the LLM service fires.
"""

import pytest
from pydantic import ValidationError

from app.models.appointment import (
    CheatsheetResponse,
    Concern,
    ProviderSummaryResponse,
    QuestionGroup,
)


class TestProviderSummaryResponse:
    def test_parses_valid_dict(self):
        # CATCHES: model not importable or constructor broken — generate_provider_summary_content
        # would crash before even trying to parse the LLM response
        data = {
            "opening": "Patient is 50, presenting with hot flashes.",
            "key_patterns": "Hot flashes co-occur with night sweats.",
        }
        m = ProviderSummaryResponse(**data)
        assert m.opening == data["opening"]
        assert m.key_patterns == data["key_patterns"]

    def test_no_symptom_picture_field(self):
        # CATCHES: symptom_picture accidentally re-added — Phase 5 removes this field
        # so the LLM no longer generates it; narrative is inserted verbatim by PDF builder
        m = ProviderSummaryResponse(opening="O")
        assert not hasattr(m, "symptom_picture")

    def test_no_closing_field(self):
        # CATCHES: closing accidentally re-added — removed alongside "Next Steps"
        # PDF section; the PDF no longer renders a closing section
        m = ProviderSummaryResponse(opening="O")
        assert not hasattr(m, "closing")

    def test_key_patterns_defaults_to_empty(self):
        # CATCHES: key_patterns required with no default — LLM sometimes omits
        # this section when no co-occurrence patterns exist, causing a crash
        m = ProviderSummaryResponse(opening="O")
        assert m.key_patterns == ""

    def test_ignores_extra_fields(self):
        # CATCHES: extra="forbid" — any unexpected LLM field (e.g. "confidence_score")
        # would raise ValidationError instead of being silently dropped
        m = ProviderSummaryResponse(
            opening="O",
            unexpected_llm_field="value",  # type: ignore
            another_extra="123",  # type: ignore
        )
        assert m.opening == "O"

    def test_missing_opening_raises_validation_error(self):
        # CATCHES: extra="ignore" also allowing missing required fields — a corrupt
        # LLM response with no "opening" would silently produce an empty PDF section
        with pytest.raises(ValidationError):
            ProviderSummaryResponse(key_patterns="K")  # type: ignore


class TestConcern:
    def test_parses_text_only(self):
        # CATCHES: Concern not importable or constructor broken — save_concerns
        # would crash converting the incoming list before any DB write
        c = Concern(text="Joint pain")
        assert c.text == "Joint pain"
        assert c.comment is None

    def test_parses_with_comment(self):
        # CATCHES: comment field missing — concern context provided by user
        # would be silently dropped, defeating the purpose of Phase 5 Area 3
        c = Concern(text="Joint pain", comment="Can't get through a workday without it")
        assert c.comment == "Can't get through a workday without it"

    def test_comment_defaults_to_none(self):
        # CATCHES: comment required with no default — existing concerns from Step 3
        # (which have no comment) would fail to parse, breaking the flow
        c = Concern(text="Sleep issues")
        assert c.comment is None

    def test_missing_text_raises_validation_error(self):
        # CATCHES: text optional — a concern with no text would produce a blank
        # bullet point in PDFs and empty entries in the LLM prompt
        with pytest.raises(ValidationError):
            Concern()  # type: ignore


class TestCheatsheetResponse:
    def test_parses_valid_dict(self):
        # CATCHES: model not importable — generate_cheatsheet_content would crash
        # before parsing the LLM JSON response
        data = {
            "opening_statement": "I am 50. My urgent concern is hot flashes.",
            "question_groups": [
                {
                    "topic": "Hot flashes",
                    "questions": ["Could you help me understand..."],
                }
            ],
        }
        m = CheatsheetResponse(**data)
        assert m.opening_statement == data["opening_statement"]

    def test_question_groups_defaults_to_empty(self):
        # CATCHES: question_groups required — LLM sometimes returns no questions
        # for minimal context, which would crash the cheatsheet PDF builder
        m = CheatsheetResponse(opening_statement="I am 50.")
        assert m.question_groups == []

    def test_ignores_extra_fields(self):
        # CATCHES: extra="forbid" — LLM frequently adds explanatory fields not
        # in the schema; these would crash parsing instead of being dropped
        m = CheatsheetResponse(
            opening_statement="O",
            unexpected_field="x",
        )
        assert m.opening_statement == "O"

    def test_missing_opening_statement_raises_validation_error(self):
        # CATCHES: opening_statement optional by mistake — cheatsheet PDF would
        # open with a blank first section rather than hard-failing for retry
        with pytest.raises(ValidationError):
            CheatsheetResponse()


class TestQuestionGroup:
    def test_parses_valid_dict(self):
        # CATCHES: QuestionGroup not importable or constructor broken — CheatsheetResponse
        # parsing would fail when question_groups contains group objects
        qg = QuestionGroup(
            topic="Hot flashes",
            questions=["Could you help me understand why..."],
        )
        assert qg.topic == "Hot flashes"
        assert len(qg.questions) == 1

    def test_ignores_extra_fields(self):
        # CATCHES: extra="forbid" on sub-model — LLM may include "rationale" or
        # other explanation fields alongside topic/questions
        qg = QuestionGroup(
            topic="Sleep",
            questions=["What might explain my insomnia?"],
            extra_llm_field="ignored",
        )
        assert qg.topic == "Sleep"

    def test_missing_topic_raises_validation_error(self):
        # CATCHES: topic optional — question groups without topic labels can't be
        # rendered in the cheatsheet PDF section headers
        with pytest.raises(ValidationError):
            QuestionGroup(questions=["A question"])

    def test_missing_questions_raises_validation_error(self):
        # CATCHES: questions optional — an empty question group would add a blank
        # section header to the PDF with no content
        with pytest.raises(ValidationError):
            QuestionGroup(topic="Sleep")
