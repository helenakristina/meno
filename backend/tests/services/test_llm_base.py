"""Tests for LLMService.

Tests the service layer in isolation with mocked LLM providers.
The mocks simulate various provider behaviors: success, timeout, errors, empty responses.
"""

import pytest
from unittest.mock import AsyncMock

from app.services.llm_base import LLMService


@pytest.fixture
def mock_provider():
    """Create a mocked LLM provider for testing."""
    return AsyncMock()


class TestLLMServiceChatCompletion:
    """Tests for LLMService.chat_completion()."""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_provider):
        """Test successful chat completion."""
        mock_provider.chat_completion.return_value = "This is a response."
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="You are helpful.",
            user_prompt="What is menopause?",
            max_tokens=256,
            temperature=0.7,
        )

        assert response == "This is a response."
        mock_provider.chat_completion.assert_called_once_with(
            system_prompt="You are helpful.",
            user_prompt="What is menopause?",
            max_tokens=256,
            temperature=0.7,
        )

    @pytest.mark.asyncio
    async def test_chat_completion_with_defaults(self, mock_provider):
        """Test that default max_tokens and temperature are applied."""
        mock_provider.chat_completion.return_value = "Response with defaults."
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        assert response == "Response with defaults."
        mock_provider.chat_completion.assert_called_once_with(
            system_prompt="Role.",
            user_prompt="Question?",
            max_tokens=1024,  # default
            temperature=0.7,  # default
        )

    @pytest.mark.asyncio
    async def test_chat_completion_with_high_temperature(self, mock_provider):
        """Test creative response with high temperature."""
        mock_provider.chat_completion.return_value = "Creative response!"
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="Be creative.",
            user_prompt="Tell a story.",
            temperature=1.8,
        )

        assert response == "Creative response!"
        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["temperature"] == 1.8

    @pytest.mark.asyncio
    async def test_chat_completion_with_deterministic_temperature(self, mock_provider):
        """Test deterministic response with temperature=0."""
        mock_provider.chat_completion.return_value = "Deterministic answer."
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="Be precise.",
            user_prompt="Calculate.",
            temperature=0,
        )

        assert response == "Deterministic answer."
        call_args = mock_provider.chat_completion.call_args
        assert call_args.kwargs["temperature"] == 0

    @pytest.mark.asyncio
    async def test_chat_completion_empty_system_prompt_raises_valueerror(
        self, mock_provider
    ):
        """Test that empty system_prompt raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(ValueError, match="system_prompt must be a non-empty string"):
            await service.chat_completion(
                system_prompt="",
                user_prompt="Question?",
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_empty_user_prompt_raises_valueerror(
        self, mock_provider
    ):
        """Test that empty user_prompt raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(ValueError, match="user_prompt must be a non-empty string"):
            await service.chat_completion(
                system_prompt="You are helpful.",
                user_prompt="   ",
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_non_string_system_prompt_raises_valueerror(
        self, mock_provider
    ):
        """Test that non-string system_prompt raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(ValueError, match="system_prompt must be a non-empty string"):
            await service.chat_completion(
                system_prompt=None,  # type: ignore
                user_prompt="Question?",
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_max_tokens_below_1_raises_valueerror(
        self, mock_provider
    ):
        """Test that max_tokens < 1 raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="max_tokens must be an integer between 1 and 4096"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                max_tokens=0,
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_max_tokens_above_4096_raises_valueerror(
        self, mock_provider
    ):
        """Test that max_tokens > 4096 raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="max_tokens must be an integer between 1 and 4096"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                max_tokens=5000,
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_non_integer_max_tokens_raises_valueerror(
        self, mock_provider
    ):
        """Test that non-integer max_tokens raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="max_tokens must be an integer between 1 and 4096"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                max_tokens="256",  # type: ignore
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_temperature_below_0_raises_valueerror(
        self, mock_provider
    ):
        """Test that temperature < 0 raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="temperature must be a number between 0 and 2"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                temperature=-0.1,
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_temperature_above_2_raises_valueerror(
        self, mock_provider
    ):
        """Test that temperature > 2 raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="temperature must be a number between 0 and 2"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                temperature=2.5,
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_non_numeric_temperature_raises_valueerror(
        self, mock_provider
    ):
        """Test that non-numeric temperature raises ValueError."""
        service = LLMService(provider=mock_provider)

        with pytest.raises(
            ValueError, match="temperature must be a number between 0 and 2"
        ):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
                temperature="high",  # type: ignore
            )

        mock_provider.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_completion_provider_timeout_raises_timeouterror(
        self, mock_provider
    ):
        """Test that provider TimeoutError is propagated."""
        mock_provider.chat_completion.side_effect = TimeoutError("API timeout")
        service = LLMService(provider=mock_provider)

        with pytest.raises(TimeoutError, match="API timeout"):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_provider_runtimeerror_raises_runtimeerror(
        self, mock_provider
    ):
        """Test that provider RuntimeError is propagated."""
        mock_provider.chat_completion.side_effect = RuntimeError("API unavailable")
        service = LLMService(provider=mock_provider)

        with pytest.raises(RuntimeError, match="API unavailable"):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_empty_response_raises_runtimeerror(
        self, mock_provider
    ):
        """Test that empty response from provider raises RuntimeError."""
        mock_provider.chat_completion.return_value = ""
        service = LLMService(provider=mock_provider)

        with pytest.raises(RuntimeError, match="LLM returned empty response"):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_whitespace_only_response_raises_runtimeerror(
        self, mock_provider
    ):
        """Test that whitespace-only response from provider raises RuntimeError."""
        mock_provider.chat_completion.return_value = "   \n\t  "
        service = LLMService(provider=mock_provider)

        with pytest.raises(RuntimeError, match="LLM returned empty response"):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_unexpected_error_converts_to_runtimeerror(
        self, mock_provider
    ):
        """Test that unexpected provider errors are converted to RuntimeError."""
        mock_provider.chat_completion.side_effect = ValueError("Unexpected")
        service = LLMService(provider=mock_provider)

        with pytest.raises(RuntimeError, match="Unexpected LLM error"):
            await service.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_long_response(self, mock_provider):
        """Test handling of long responses from provider."""
        long_response = "A" * 8000  # Very long response
        mock_provider.chat_completion.return_value = long_response
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
            max_tokens=4096,
        )

        assert response == long_response
        assert len(response) == 8000

    @pytest.mark.asyncio
    async def test_chat_completion_with_special_characters(self, mock_provider):
        """Test handling of special characters in prompts and responses."""
        special_response = "Response with émojis 🎯 and spëcial çhars!"
        mock_provider.chat_completion.return_value = special_response
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="You are helpful. Respond in UTF-8. Special: 你好",
            user_prompt="What about café? 🤔",
        )

        assert response == special_response

    @pytest.mark.asyncio
    async def test_chat_completion_newlines_in_response(self, mock_provider):
        """Test handling of multi-line responses."""
        multiline_response = "Line 1.\n\nLine 2.\n\nLine 3."
        mock_provider.chat_completion.return_value = multiline_response
        service = LLMService(provider=mock_provider)

        response = await service.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        assert response == multiline_response
        assert response.count("\n") == 4
