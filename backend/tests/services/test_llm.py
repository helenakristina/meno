"""Tests for LLMService.

Tests the service layer in isolation with mocked LLM providers.
Covers symptom summary generation, provider questions, and calling scripts.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock

from app.models.symptoms import SymptomFrequency, SymptomPair
from app.services.llm import LLMService


@pytest.fixture
def mock_provider():
    """Create a mocked LLM provider for testing."""
    return AsyncMock()


@pytest.fixture
def service(mock_provider):
    """Create LLMService with mocked provider."""
    return LLMService(provider=mock_provider)


class TestLLMServiceGenerateSymptomSummary:
    """Tests for LLMService.generate_symptom_summary()."""

    @pytest.mark.asyncio
    async def test_generate_symptom_summary_success(self, service, mock_provider):
        """Test successful symptom summary generation."""
        mock_response = (
            "Data shows frequent fatigue and brain fog, which co-occurred in 70% of logs. "
            "Sleep disruption appears related to both. Recommend discussing with provider."
        )
        mock_provider.chat_completion.return_value = mock_response

        frequency_stats = [
            SymptomFrequency(symptom_id="f1", symptom_name="Fatigue", category="energy", count=18),
            SymptomFrequency(symptom_id="f2", symptom_name="Brain fog", category="cognitive", count=15),
        ]
        cooccurrence_stats = [
            SymptomPair(
                symptom1_id="f1",
                symptom1_name="Fatigue",
                symptom2_id="f2",
                symptom2_name="Brain fog",
                cooccurrence_count=12,
                cooccurrence_rate=0.70,
                total_occurrences_symptom1=18,
            )
        ]
        date_range = (date(2026, 1, 1), date(2026, 2, 1))

        result = await service.generate_symptom_summary(
            frequency_stats=frequency_stats,
            cooccurrence_stats=cooccurrence_stats,
            date_range=date_range,
        )

        assert result == mock_response
        mock_provider.chat_completion.assert_called_once()
        call_args = mock_provider.chat_completion.call_args
        assert "logs show" not in call_args.kwargs["system_prompt"].lower().split("logs")[0]  # System prompt includes "logs show"
        assert "January 01, 2026" in call_args.kwargs["user_prompt"]

    @pytest.mark.asyncio
    async def test_generate_symptom_summary_empty_stats(self, service, mock_provider):
        """Test symptom summary with empty stats."""
        mock_response = "No symptom data available to summarize."
        mock_provider.chat_completion.return_value = mock_response

        result = await service.generate_symptom_summary(
            frequency_stats=[],
            cooccurrence_stats=[],
            date_range=(date(2026, 1, 1), date(2026, 2, 1)),
        )

        assert result == mock_response
        mock_provider.chat_completion.assert_called_once()
        call_args = mock_provider.chat_completion.call_args
        assert "No symptom data available" in call_args.kwargs["user_prompt"]

    @pytest.mark.asyncio
    async def test_generate_symptom_summary_sets_temperature(self, service, mock_provider):
        """Test that summary generation uses deterministic temperature (0.3)."""
        mock_provider.chat_completion.return_value = "Summary."

        await service.generate_symptom_summary(
            frequency_stats=[],
            cooccurrence_stats=[],
            date_range=(date(2026, 1, 1), date(2026, 2, 1)),
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["temperature"] == 0.3  # Deterministic for summaries

    @pytest.mark.asyncio
    async def test_generate_symptom_summary_sets_max_tokens(self, service, mock_provider):
        """Test that summary generation uses appropriate token limit."""
        mock_provider.chat_completion.return_value = "Summary."

        await service.generate_symptom_summary(
            frequency_stats=[],
            cooccurrence_stats=[],
            date_range=(date(2026, 1, 1), date(2026, 2, 1)),
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["max_tokens"] == 600

    @pytest.mark.asyncio
    async def test_generate_symptom_summary_provider_error(self, service, mock_provider):
        """Test error handling when provider fails."""
        mock_provider.chat_completion.side_effect = RuntimeError("Provider error")

        with pytest.raises(RuntimeError, match="Provider error"):
            await service.generate_symptom_summary(
                frequency_stats=[],
                cooccurrence_stats=[],
                date_range=(date(2026, 1, 1), date(2026, 2, 1)),
            )


class TestLLMServiceGenerateProviderQuestions:
    """Tests for LLMService.generate_provider_questions()."""

    @pytest.mark.asyncio
    async def test_generate_provider_questions_success(self, service, mock_provider):
        """Test successful provider questions generation."""
        mock_response = (
            "1. Could you help me understand what causes fatigue during this time?\n"
            "2. What might explain the brain fog I've been tracking?\n"
            "3. Could hormonal changes relate to these patterns?\n"
            "4. What lifestyle factors might help with sleep disruption?\n"
            "5. Should I monitor anything else?"
        )
        mock_provider.chat_completion.return_value = mock_response

        frequency_stats = [
            SymptomFrequency(symptom_id="f1", symptom_name="Fatigue", category="energy", count=18),
        ]
        cooccurrence_stats = []

        result = await service.generate_provider_questions(
            frequency_stats=frequency_stats,
            cooccurrence_stats=cooccurrence_stats,
        )

        # Verify numbering is stripped
        assert len(result) == 5
        assert "Could you help me understand what causes fatigue" in result[0]
        assert "What might explain the brain fog" in result[1]
        assert not result[0].startswith("1.")

    @pytest.mark.asyncio
    async def test_generate_provider_questions_with_context(self, service, mock_provider):
        """Test questions generation with user context."""
        mock_response = "1. Question one?\n2. Question two?"
        mock_provider.chat_completion.return_value = mock_response

        await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
            user_context="In early perimenopause",
        )

        call_args = mock_provider.chat_completion.call_args
        assert "In early perimenopause" in call_args.kwargs["user_prompt"]

    @pytest.mark.asyncio
    async def test_generate_provider_questions_max_seven(self, service, mock_provider):
        """Test that at most 7 questions are returned."""
        # Generate 10 questions in response
        mock_response = "\n".join([f"{i+1}. Question {i+1}?" for i in range(10)])
        mock_provider.chat_completion.return_value = mock_response

        result = await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
        )

        assert len(result) <= 7

    @pytest.mark.asyncio
    async def test_generate_provider_questions_skips_empty_lines(self, service, mock_provider):
        """Test that empty lines are skipped."""
        mock_response = "1. Question one?\n\n\n2. Question two?\n\n3. Question three?"
        mock_provider.chat_completion.return_value = mock_response

        result = await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
        )

        assert len(result) == 3
        assert all(q for q in result)  # No empty strings

    @pytest.mark.asyncio
    async def test_generate_provider_questions_handles_various_numbering(
        self, service, mock_provider
    ):
        """Test handling of various number formats (1., 1), 1 )."""
        mock_response = (
            "1. First question?\n"
            "2) Second question?\n"
            "3 Third question?\n"
            "Non-numbered line"
        )
        mock_provider.chat_completion.return_value = mock_response

        result = await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
        )

        assert len(result) == 4
        assert "First question?" in result[0]
        assert "Second question?" in result[1]
        assert "Third question?" in result[2]
        assert "Non-numbered line" in result[3]

    @pytest.mark.asyncio
    async def test_generate_provider_questions_sets_temperature(self, service, mock_provider):
        """Test that questions generation uses moderate temperature (0.4)."""
        mock_provider.chat_completion.return_value = "1. Question?"

        await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["temperature"] == 0.4

    @pytest.mark.asyncio
    async def test_generate_provider_questions_sets_max_tokens(self, service, mock_provider):
        """Test that questions generation uses appropriate token limit."""
        mock_provider.chat_completion.return_value = "1. Question?"

        await service.generate_provider_questions(
            frequency_stats=[],
            cooccurrence_stats=[],
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["max_tokens"] == 500


class TestLLMServiceGenerateCallingScript:
    """Tests for LLMService.generate_calling_script()."""

    @pytest.mark.asyncio
    async def test_generate_calling_script_success(self, service, mock_provider):
        """Test successful calling script generation."""
        mock_response = (
            "Hi, I'd like to schedule an appointment. I've been tracking my symptoms "
            "and have some patterns I'd like to discuss with you."
        )
        mock_provider.chat_completion.return_value = mock_response

        system_prompt = "You are helping someone prepare to call a healthcare provider."
        user_prompt = "Generate a script for calling Dr. Smith's office about perimenopause symptoms."

        result = await service.generate_calling_script(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        assert result == mock_response
        mock_provider.chat_completion.assert_called_once_with(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=300,
            temperature=0.7,
        )

    @pytest.mark.asyncio
    async def test_generate_calling_script_sets_temperature(self, service, mock_provider):
        """Test that calling script uses creative temperature (0.7)."""
        mock_provider.chat_completion.return_value = "Script."

        await service.generate_calling_script(
            system_prompt="System.",
            user_prompt="Generate script.",
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["temperature"] == 0.7  # Creative for scripts

    @pytest.mark.asyncio
    async def test_generate_calling_script_sets_max_tokens(self, service, mock_provider):
        """Test that calling script uses appropriate token limit."""
        mock_provider.chat_completion.return_value = "Script."

        await service.generate_calling_script(
            system_prompt="System.",
            user_prompt="Generate script.",
        )

        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["max_tokens"] == 300

    @pytest.mark.asyncio
    async def test_generate_calling_script_provider_error(self, service, mock_provider):
        """Test error handling when provider fails."""
        mock_provider.chat_completion.side_effect = TimeoutError("Request timeout")

        with pytest.raises(TimeoutError):
            await service.generate_calling_script(
                system_prompt="System.",
                user_prompt="Generate script.",
            )


class TestLLMServiceInitialization:
    """Tests for LLMService initialization and provider injection."""

    def test_llm_service_init(self, mock_provider):
        """Test that LLMService initializes with provider."""
        service = LLMService(provider=mock_provider)
        assert service.provider is mock_provider

    def test_llm_service_provider_type(self, mock_provider):
        """Test that provider is stored correctly."""
        service = LLMService(provider=mock_provider)
        assert hasattr(service, "provider")
        assert service.provider == mock_provider
