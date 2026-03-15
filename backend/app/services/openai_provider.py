"""OpenAI implementation of the LLMProvider protocol.

Wraps the OpenAI API (text-davinci-003 or gpt-4o-mini for development) with error
handling and logging. Can be swapped out for other providers (Anthropic, etc.)
without changing calling code.
"""

import logging
from openai import AsyncOpenAI

from app.services.llm_base import LLMProvider
from app.utils.retry import retry_transient

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLMProvider.

    Provides chat completions using the OpenAI API. Handles connection errors,
    API errors, and response validation.

    Suitable for development and production use. For development, gpt-4o-mini
    is cost-effective. For production with higher accuracy needs, switch to gpt-4o.
    """

    def __init__(self, api_key: str):
        """Initialize with OpenAI API key.

        Args:
            api_key: OpenAI API key (e.g., sk-...). Should be kept secret.
                Load from environment variables (OPENAI_API_KEY).
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Cost-effective for development

    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Generate a chat completion using OpenAI.

        Automatically retries transient failures (timeouts, rate limits) with
        exponential backoff. See app/utils/retry.py for retry logic.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in response (1–4096).
            temperature: Sampling temperature (0–2).
            response_format: Output format hint. "json" enables JSON mode (OpenAI only).
                None (default) returns plain text.

        Returns:
            The completed text response from OpenAI.

        Raises:
            TimeoutError: If the API request times out.
            RuntimeError: If the API returns an error or the response is empty.
        """
        try:
            logger.debug(
                "OpenAI request: model=%s max_tokens=%d temperature=%.1f response_format=%s",
                self.model,
                max_tokens,
                temperature,
                response_format or "text",
            )

            # Build request kwargs
            create_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Add response_format if specified (OpenAI supports JSON mode)
            if response_format == "json":
                create_kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**create_kwargs)

            # Extract response text safely
            if not response.choices:
                logger.error("OpenAI returned no message choices")
                raise RuntimeError("OpenAI returned no message content")

            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.error("OpenAI returned empty message content")
                raise RuntimeError("OpenAI returned no message content")

            logger.info(
                "OpenAI response: model=%s tokens=%s",
                response.model,
                response.usage.completion_tokens if response.usage else None,
            )
            return text

        except TimeoutError as e:
            logger.error("OpenAI request timeout: %s", e, exc_info=True)
            raise
        except RuntimeError as e:
            logger.error("OpenAI runtime error: %s", e, exc_info=True)
            raise
        except Exception as e:
            # Catch OpenAI-specific errors (APIError, RateLimitError, etc.)
            logger.error("OpenAI API error: %s", e, exc_info=True)
            raise RuntimeError(f"OpenAI API error: {e}") from e

    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def chat_completion_with_usage(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.5,
        response_format: str | None = None,
    ) -> tuple[str, int, int]:
        """Generate a chat completion and return usage information.

        Automatically retries transient failures (timeouts, rate limits) with
        exponential backoff. See app/utils/retry.py for retry logic.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in response (1–4096).
            temperature: Sampling temperature (0–2).
            response_format: Output format hint. "json" enables JSON mode (OpenAI only).
                None (default) returns plain text.

        Returns:
            Tuple of (response_text, prompt_tokens, completion_tokens).

        Raises:
            TimeoutError: If the API request times out.
            RuntimeError: If the API returns an error or the response is empty.
        """
        try:
            logger.debug(
                "OpenAI request with usage: model=%s max_tokens=%d temperature=%.1f response_format=%s",
                self.model,
                max_tokens,
                temperature,
                response_format or "text",
            )

            # Build request kwargs
            create_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Add response_format if specified (OpenAI supports JSON mode)
            if response_format == "json":
                create_kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**create_kwargs)

            # Extract response text safely
            if not response.choices:
                logger.error("OpenAI returned no message choices")
                raise RuntimeError("OpenAI returned no message content")

            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.error("OpenAI returned empty message content")
                raise RuntimeError("OpenAI returned no message content")

            # Extract token usage
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = (
                response.usage.completion_tokens if response.usage else 0
            )

            logger.info(
                "OpenAI response: model=%s prompt_tokens=%d completion_tokens=%d",
                response.model,
                prompt_tokens,
                completion_tokens,
            )
            return text, prompt_tokens, completion_tokens

        except TimeoutError as e:
            logger.error("OpenAI request timeout: %s", e, exc_info=True)
            raise
        except RuntimeError as e:
            logger.error("OpenAI runtime error: %s", e, exc_info=True)
            raise
        except Exception as e:
            # Catch OpenAI-specific errors (APIError, RateLimitError, etc.)
            logger.error("OpenAI API error: %s", e, exc_info=True)
            raise RuntimeError(f"OpenAI API error: {e}") from e
