"""OpenAI implementation of the LLMProvider protocol.

Wraps the OpenAI API (text-davinci-003 or gpt-4o-mini for development) with error
handling and logging. Can be swapped out for other providers (Anthropic, etc.)
without changing calling code.
"""

import logging
from openai import AsyncOpenAI

from app.services.llm_base import LLMProvider

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
        self.model = "gpt-4o-mini"  # Cost-effective for development

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion using OpenAI.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in response (1–4096).
            temperature: Sampling temperature (0–2).

        Returns:
            The completed text response from OpenAI.

        Raises:
            TimeoutError: If the API request times out.
            RuntimeError: If the API returns an error or the response is empty.
        """
        try:
            logger.debug(
                "OpenAI request: model=%s max_tokens=%d temperature=%.1f",
                self.model,
                max_tokens,
                temperature,
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

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

    async def chat_completion_with_usage(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.5,
    ) -> tuple[str, int, int]:
        """Generate a chat completion and return usage information.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in response (1–4096).
            temperature: Sampling temperature (0–2).

        Returns:
            Tuple of (response_text, prompt_tokens, completion_tokens).

        Raises:
            TimeoutError: If the API request times out.
            RuntimeError: If the API returns an error or the response is empty.
        """
        try:
            logger.debug(
                "OpenAI request with usage: model=%s max_tokens=%d temperature=%.1f",
                self.model,
                max_tokens,
                temperature,
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

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
            completion_tokens = response.usage.completion_tokens if response.usage else 0

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
