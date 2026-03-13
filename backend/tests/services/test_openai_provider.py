"""Tests for OpenAIProvider.

Tests the OpenAI implementation of LLMProvider with mocked OpenAI API calls.
Covers success paths, error handling, and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.openai_provider import OpenAIProvider


@pytest.fixture
def mock_openai_client():
    """Create a mocked OpenAI AsyncClient."""
    return AsyncMock()


@pytest.fixture
def provider(mock_openai_client, monkeypatch):
    """Create OpenAIProvider with mocked OpenAI client."""
    # Mock AsyncOpenAI constructor to return our mocked client
    # Use MagicMock, not AsyncMock, for the constructor
    mock_openai_class = MagicMock(return_value=mock_openai_client)
    monkeypatch.setattr(
        "app.services.openai_provider.AsyncOpenAI",
        mock_openai_class,
    )
    return OpenAIProvider(api_key="test-key-123")


class TestOpenAIProviderChatCompletion:
    """Tests for OpenAIProvider.chat_completion()."""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, provider, mock_openai_client):
        """Test successful chat completion from OpenAI."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="This is OpenAI's response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(completion_tokens=42)
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="You are helpful.",
            user_prompt="What is menopause?",
            max_tokens=256,
            temperature=0.7,
        )

        assert response == "This is OpenAI's response."
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_defaults(self, provider, mock_openai_client):
        """Test chat completion with default parameters."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Default response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        assert response == "Default response."
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 1024  # default
        assert call_args.kwargs["temperature"] == 0.7  # default

    @pytest.mark.asyncio
    async def test_chat_completion_sends_correct_messages(
        self, provider, mock_openai_client
    ):
        """Test that system_prompt and user_prompt are sent correctly."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        await provider.chat_completion(
            system_prompt="Be concise.",
            user_prompt="Explain X.",
        )

        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be concise."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Explain X."

    @pytest.mark.asyncio
    async def test_chat_completion_uses_correct_model(
        self, provider, mock_openai_client
    ):
        """Test that the correct OpenAI model is used."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        await provider.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_tokens_and_temperature(
        self, provider, mock_openai_client
    ):
        """Test with custom max_tokens and temperature."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Creative response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        await provider.chat_completion(
            system_prompt="Be creative.",
            user_prompt="Generate ideas.",
            max_tokens=2048,
            temperature=1.5,
        )

        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 2048
        assert call_args.kwargs["temperature"] == 1.5

    @pytest.mark.asyncio
    async def test_chat_completion_no_choices_raises_runtimeerror(
        self, provider, mock_openai_client
    ):
        """Test that empty choices list raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_openai_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no message content"):
            await provider.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_no_content_raises_runtimeerror(
        self, provider, mock_openai_client
    ):
        """Test that None message content raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no message content"):
            await provider.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_empty_content_raises_runtimeerror(
        self, provider, mock_openai_client
    ):
        """Test that empty string content raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no message content"):
            await provider.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_timeout_raises_timeouterror(
        self, provider, mock_openai_client
    ):
        """Test that OpenAI timeout is propagated as TimeoutError."""
        mock_openai_client.chat.completions.create.side_effect = TimeoutError(
            "Request timed out"
        )

        with pytest.raises(TimeoutError):
            await provider.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_api_error_raises_runtimeerror(
        self, provider, mock_openai_client
    ):
        """Test that OpenAI API errors are converted to RuntimeError."""
        # Simulate a generic OpenAI API error
        mock_openai_client.chat.completions.create.side_effect = Exception(
            "Rate limit exceeded"
        )

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await provider.chat_completion(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_preserves_response_formatting(
        self, provider, mock_openai_client
    ):
        """Test that response formatting (newlines, etc.) is preserved."""
        formatted_response = "Line 1.\n\nLine 2.\n\nLine 3."
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=formatted_response))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Preserve formatting.",
            user_prompt="Question?",
        )

        assert response == formatted_response
        assert response.count("\n") == 4

    @pytest.mark.asyncio
    async def test_chat_completion_handles_special_characters(
        self, provider, mock_openai_client
    ):
        """Test that special characters in response are preserved."""
        special_response = "UTF-8: café, 你好, émoji 🎯"
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=special_response))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Support UTF-8.",
            user_prompt="Generate text with special characters.",
        )

        assert response == special_response
        assert "café" in response
        assert "你好" in response
        assert "🎯" in response

    @pytest.mark.asyncio
    async def test_chat_completion_long_response(self, provider, mock_openai_client):
        """Test handling of very long responses."""
        long_response = "A" * 10000
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=long_response))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(completion_tokens=9999)
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Generate long text.",
            user_prompt="Generate 10k characters.",
            max_tokens=4096,
        )

        assert response == long_response
        assert len(response) == 10000

    @pytest.mark.asyncio
    async def test_chat_completion_handles_missing_usage(
        self, provider, mock_openai_client
    ):
        """Test that missing usage stats don't cause errors."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response without usage stats."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None  # No usage stats provided
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        assert response == "Response without usage stats."

    @pytest.mark.asyncio
    async def test_chat_completion_initializes_with_correct_api_key(
        self, mock_openai_client, monkeypatch
    ):
        """Test that provider is initialized with the correct API key."""
        # Use MagicMock for constructor (not AsyncMock - constructors aren't async)
        mock_openai_class = MagicMock(return_value=mock_openai_client)
        monkeypatch.setattr(
            "app.services.openai_provider.AsyncOpenAI",
            mock_openai_class,
        )

        provider = OpenAIProvider(api_key="sk-secret-key-123")

        # Verify AsyncOpenAI was initialized with the key
        mock_openai_class.assert_called_once_with(api_key="sk-secret-key-123")

    @pytest.mark.asyncio
    async def test_chat_completion_model_field_is_set(self, provider):
        """Test that provider.model field is set correctly."""
        assert provider.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_chat_completion_client_field_is_set(self, provider):
        """Test that provider.client is the mocked AsyncOpenAI."""
        assert provider.client is not None

    @pytest.mark.asyncio
    async def test_chat_completion_with_json_response_format(self, provider, mock_openai_client):
        """Test chat completion with JSON response format."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"result": "JSON response"}'))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(completion_tokens=50)
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = await provider.chat_completion(
            system_prompt="Return JSON.",
            user_prompt="Generate JSON.",
            response_format="json",
        )

        assert response == '{"result": "JSON response"}'
        call_args = mock_openai_client.chat.completions.create.call_args
        assert "response_format" in call_args.kwargs
        assert call_args.kwargs["response_format"]["type"] == "json_object"


class TestOpenAIProviderChatCompletionWithUsage:
    """Tests for OpenAIProvider.chat_completion_with_usage()."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mocked OpenAI AsyncClient."""
        return AsyncMock()

    @pytest.fixture
    def provider(self, mock_openai_client, monkeypatch):
        """Create OpenAIProvider with mocked OpenAI client."""
        mock_openai_class = MagicMock(return_value=mock_openai_client)
        monkeypatch.setattr(
            "app.services.openai_provider.AsyncOpenAI",
            mock_openai_class,
        )
        return OpenAIProvider(api_key="test-key-123")

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_success(self, provider, mock_openai_client):
        """Test successful chat completion with usage info."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response with usage."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
        mock_openai_client.chat.completions.create.return_value = mock_response

        text, prompt_tokens, completion_tokens = await provider.chat_completion_with_usage(
            system_prompt="You are helpful.",
            user_prompt="What is this?",
        )

        assert text == "Response with usage."
        assert prompt_tokens == 100
        assert completion_tokens == 50

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_no_usage_info(self, provider, mock_openai_client):
        """Test with_usage when usage info is None."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None  # No usage info
        mock_openai_client.chat.completions.create.return_value = mock_response

        text, prompt_tokens, completion_tokens = await provider.chat_completion_with_usage(
            system_prompt="Role.",
            user_prompt="Question?",
        )

        assert text == "Response."
        assert prompt_tokens == 0  # Defaults to 0
        assert completion_tokens == 0

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_custom_params(self, provider, mock_openai_client):
        """Test with_usage with custom max_tokens and temperature."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Custom response."))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=75, completion_tokens=25)
        mock_openai_client.chat.completions.create.return_value = mock_response

        text, prompt_tokens, completion_tokens = await provider.chat_completion_with_usage(
            system_prompt="Be specific.",
            user_prompt="Describe X.",
            max_tokens=2000,
            temperature=1.2,
        )

        assert text == "Custom response."
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 2000
        assert call_args.kwargs["temperature"] == 1.2

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_json_format(self, provider, mock_openai_client):
        """Test with_usage with JSON response format."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"key": "value"}'))
        ]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=80, completion_tokens=20)
        mock_openai_client.chat.completions.create.return_value = mock_response

        text, prompt_tokens, completion_tokens = await provider.chat_completion_with_usage(
            system_prompt="JSON mode.",
            user_prompt="Generate JSON.",
            response_format="json",
        )

        assert text == '{"key": "value"}'
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"]["type"] == "json_object"

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_no_choices(self, provider, mock_openai_client):
        """Test error when with_usage gets no choices."""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_openai_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no message content"):
            await provider.chat_completion_with_usage(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_empty_content(self, provider, mock_openai_client):
        """Test error when with_usage gets empty content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no message content"):
            await provider.chat_completion_with_usage(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_timeout(self, provider, mock_openai_client):
        """Test timeout error in with_usage."""
        mock_openai_client.chat.completions.create.side_effect = TimeoutError("Timeout")

        with pytest.raises(TimeoutError):
            await provider.chat_completion_with_usage(
                system_prompt="Role.",
                user_prompt="Question?",
            )

    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_api_error(self, provider, mock_openai_client):
        """Test API error in with_usage."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API error")

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await provider.chat_completion_with_usage(
                system_prompt="Role.",
                user_prompt="Question?",
            )
