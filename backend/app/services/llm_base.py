"""LLM integration service for chat completions.

Abstracts away the choice of LLM provider (OpenAI, Claude, etc.) behind a unified
interface. The service handles retries, error handling, and logging — callers just
pass system/user prompts and get back text responses.

This design enables easy provider swapping (development vs production) without
changing route code. The LLMProvider protocol defines the contract; concrete
implementations (OpenAIProvider, AnthropicProvider) plug in via dependency injection.
"""

# TODO: V2.1 - Streaming & Structured Output
# The following improvements are planned for V2.1:
# - Add stream_completion() method for streaming long-running LLM calls
# - Implement true structured outputs (response_format="json" with JSON schema)
# - This will improve UX for narrative generation (Step 2) and scenarios (Step 4)
#   where users currently wait 10-20 seconds for responses
# - Streaming will buffer chunks and return complete response (initially)

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Contract for an LLM provider implementation.

    Concrete implementations (OpenAIProvider, AnthropicProvider, etc.) must
    subclass this ABC to be injectable into LLMService.
    """

    @abstractmethod
    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Generate a chat completion response.

        Args:
            system_prompt: System-level instructions (role, behavior, constraints).
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in the response (1–4096). Defaults to 1024.
            temperature: Sampling temperature (0–2). 0 is deterministic, 2 is most random.
                Defaults to 0.7 (balanced).
            response_format: Output format hint. "json" for structured JSON output.
                None (default) returns plain text.
                V2.1 will implement true structured outputs with JSON schema validation.

        Returns:
            The completed text response from the LLM.

        Raises:
            ValueError: If arguments are invalid (e.g., max_tokens out of range).
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or the response is empty.
        """
        pass


class LLMService:
    """Service layer for LLM-powered chat completions.

    Provides a unified interface for chat completions regardless of the underlying
    LLM provider. Handles error handling, logging, and input validation.

    No database access — purely stateless logic. Callers provide all necessary
    context (system prompt, user prompt, history) directly.
    """

    def __init__(self, provider: LLMProvider):
        """Initialize with an LLM provider.

        Args:
            provider: An implementation of the LLMProvider protocol (dependency-injected).
        """
        self.provider = provider

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion response.

        Delegates to the injected provider, adding logging and error handling.

        Args:
            system_prompt: System-level instructions defining behavior and constraints.
                For Ask Meno: core identity (who we are), source grounding (cite docs),
                behavioral guardrails (no medical advice), and dynamic context (user stage,
                cached symptoms, RAG chunks).
            user_prompt: User's question or message. Should not contain raw PII — use
                anonymized format (e.g., "Day 3, Day 7" instead of actual dates).
            max_tokens: Maximum tokens in response (1–4096). Defaults to 1024.
            temperature: Sampling temperature (0–2). 0 is deterministic, 1 is balanced,
                2 is most creative. Defaults to 0.7.

        Returns:
            The completed text response from the LLM.

        Raises:
            ValueError: If arguments fail validation (e.g., max_tokens < 1, temperature < 0).
            TimeoutError: If the LLM API times out (connection, response latency).
            RuntimeError: If the LLM API returns an error, empty response, or is unavailable.
        """
        # Validate inputs early — any ValueError here is a validation error
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("system_prompt must be a non-empty string")
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("user_prompt must be a non-empty string")
        if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 4096:
            raise ValueError("max_tokens must be an integer between 1 and 4096")
        if (
            not isinstance(temperature, (int, float))
            or temperature < 0
            or temperature > 2
        ):
            raise ValueError("temperature must be a number between 0 and 2")

        # Call provider with separate exception handling for provider errors
        try:
            logger.debug(
                "LLM chat completion: max_tokens=%d temperature=%.1f",
                max_tokens,
                temperature,
            )
            response = await self.provider.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if not response or not response.strip():
                logger.error("LLM returned empty response")
                raise RuntimeError("LLM returned empty response")

            logger.info(
                "LLM chat completion succeeded: response_length=%d",
                len(response),
            )
            return response

        except TimeoutError as e:
            # LLM API timeout — likely transient, could be retried
            logger.error("LLM API timeout: %s", e, exc_info=True)
            raise
        except RuntimeError as e:
            # LLM API error (unavailable, error response, etc.)
            logger.error("LLM API error: %s", e, exc_info=True)
            raise
        except Exception as e:
            # Unexpected error from provider — log and convert to RuntimeError
            logger.error("Unexpected LLM error: %s", e, exc_info=True)
            raise RuntimeError(f"Unexpected LLM error: {e}") from e
