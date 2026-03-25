"""Tests for PromptService.build_system_prompt().

Verifies the five-layer assembly, dynamic context injection, and voice examples.
"""

from app.services.prompts import PromptService


SAMPLE_CHUNKS = [
    {
        "source_url": "https://menopausewiki.ca/overview",
        "title": "Perimenopause Overview",
        "section_name": "Definition",
        "content": "Perimenopause is the transition to menopause.",
    },
    {
        "source_url": "https://menopause.org/hrt-guidelines",
        "title": "HRT Guidelines 2023",
        "section_name": "Recommendations",
        "content": "Current evidence supports HRT for eligible women.",
    },
]


def _build(**kwargs) -> str:
    defaults = dict(
        journey_stage="perimenopause",
        age=48,
        symptom_summary="Hot flashes logged frequently.",
        chunks=SAMPLE_CHUNKS,
    )
    defaults.update(kwargs)
    return PromptService.build_system_prompt(**defaults)


class TestFiveLayerAssembly:
    # CATCHES: voice layer accidentally dropped from assembled prompt
    def test_build_system_prompt_when_called_then_all_five_layers_present(self):
        prompt = _build()
        assert "RESPONSE FORMAT:" in prompt  # LAYER_3_SOURCE_RULES
        assert "YOUR VOICE:" in prompt  # LAYER_2_VOICE
        assert "IN SCOPE" in prompt  # LAYER_4_SCOPE
        assert "User context:" in prompt  # Layer 5 (dynamic)

    # CATCHES: before/after voice examples removed accidentally
    def test_build_system_prompt_when_called_then_voice_examples_present(self):
        prompt = _build()
        assert "Instead of:" in prompt

    # CATCHES: identity layer dropped
    def test_build_system_prompt_when_called_then_identity_layer_present(self):
        prompt = _build()
        assert "You are Meno" in prompt

    # CATCHES: layers joined without separator (text runs together)
    def test_build_system_prompt_when_called_then_layers_separated_by_double_newline(
        self,
    ):
        prompt = _build()
        assert "\n\n" in prompt

    # CATCHES: one-source rule accidentally removed from prompt
    def test_build_system_prompt_when_called_then_one_source_rule_present(self):
        prompt = _build()
        assert (
            "ONE-SOURCE RULE" in prompt
            or "one source" in prompt.lower()
            or "ONE SOURCE" in prompt
        )

    # CATCHES: new v2 schema not reflected in prompt (still shows claims[])
    def test_build_system_prompt_when_called_then_v2_schema_fields_present_and_v1_absent(
        self,
    ):
        prompt = _build()
        assert '"body"' in prompt
        assert '"source_index"' in prompt
        assert '"claims"' not in prompt
        assert '"source_indices"' not in prompt


class TestDynamicContextLayer:
    # CATCHES: journey stage not injected into prompt
    def test_build_system_prompt_when_journey_stage_postmenopause_then_stage_in_prompt(
        self,
    ):
        prompt = _build(journey_stage="postmenopause")
        assert "postmenopause" in prompt

    # CATCHES: age not injected into prompt
    def test_build_system_prompt_when_age_provided_then_age_in_prompt(self):
        prompt = _build(age=52)
        assert "52" in prompt

    # CATCHES: unknown age crashes build_system_prompt
    def test_build_system_prompt_when_age_is_none_then_unknown_in_prompt(self):
        prompt = _build(age=None)
        assert "unknown" in prompt

    # CATCHES: RAG chunks not included in prompt
    def test_build_system_prompt_when_chunks_provided_then_chunk_titles_in_prompt(self):
        prompt = _build()
        assert "Perimenopause Overview" in prompt
        assert "HRT Guidelines 2023" in prompt

    # CATCHES: source count wrong (off-by-one or missing entirely)
    def test_build_system_prompt_when_two_chunks_provided_then_source_count_is_two(
        self,
    ):
        prompt = _build(chunks=SAMPLE_CHUNKS)
        assert "2 source" in prompt

    # CATCHES: cycle context dropped when provided
    def test_build_system_prompt_when_cycle_context_provided_then_cycle_data_in_prompt(
        self,
    ):
        prompt = _build(
            cycle_context={
                "average_cycle_length": 28,
                "months_since_last_period": 3,
                "inferred_stage": "perimenopause",
            }
        )
        assert "28" in prompt
        assert "months since last period: 3" in prompt.lower()


class TestSanitizePromptField:
    # CATCHES: newline injection left intact in prompt fields
    def test_sanitize_prompt_field_when_newline_in_value_then_replaced_with_space(self):
        result = PromptService._sanitize_prompt_field("foo\nbar")
        assert "\n" not in result
        assert "foo bar" == result

    # CATCHES: carriage return injection left intact
    def test_sanitize_prompt_field_when_carriage_return_in_value_then_replaced_with_space(
        self,
    ):
        result = PromptService._sanitize_prompt_field("foo\rbar")
        assert "\r" not in result
        assert "foo bar" == result

    # CATCHES: truncation not applied, allowing oversized injection payloads
    def test_sanitize_prompt_field_when_value_exceeds_max_len_then_truncated(self):
        long_value = "a" * 200
        result = PromptService._sanitize_prompt_field(long_value, max_len=100)
        assert len(result) == 100

    # CATCHES: whitespace padding surviving into prompt fields
    def test_sanitize_prompt_field_when_leading_trailing_whitespace_then_stripped(self):
        result = PromptService._sanitize_prompt_field("  hello  ")
        assert result == "hello"

    # CATCHES: combined attack (newlines + oversized) not fully neutralized
    def test_sanitize_prompt_field_when_newline_and_oversized_then_both_neutralized(
        self,
    ):
        value = "safe\ninjection payload " + "x" * 200
        result = PromptService._sanitize_prompt_field(value, max_len=50)
        assert "\n" not in result
        assert len(result) <= 50

    # CATCHES: default max_len changed unintentionally
    def test_sanitize_prompt_field_when_no_max_len_specified_then_default_is_100(self):
        long_value = "b" * 200
        result = PromptService._sanitize_prompt_field(long_value)
        assert len(result) == 100
