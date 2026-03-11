"""Retry utilities for external API calls.

Provides decorators and context managers for retrying transient failures
with exponential backoff. Used for LLM calls, Supabase queries, and other
external integrations.

Philosophy: Retry fast for the first few attempts, then back off to avoid
hammering a failing service. Don't retry permanent failures (auth errors, 404s).
"""

import logging
from typing import Callable, TypeVar
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient errors worth retrying
RETRYABLE_ERRORS = (
    TimeoutError,
    ConnectionError,
    OSError,  # Network errors
)


def is_retryable_exception(exc: Exception) -> bool:
    """Determine if exception is transient (worth retrying).

    Args:
        exc: Exception to check.

    Returns:
        True if exception is transient (retry recommended).
    """
    # Retry network/timeout errors
    if isinstance(exc, RETRYABLE_ERRORS):
        return True

    # Retry OpenAI rate limit errors (429)
    # OpenAI raises APIError with status_code
    if hasattr(exc, "status_code") and exc.status_code == 429:  # type: ignore
        return True

    # Retry on "Connection reset by peer" and similar
    if "Connection" in str(exc) or "timeout" in str(exc).lower():
        return True

    # Don't retry auth errors, 400s, 404s
    if hasattr(exc, "status_code") and exc.status_code in (401, 403, 404, 400):  # type: ignore
        return False

    return False


def retry_transient(
    max_attempts: int = 3,
    initial_wait: int = 1,
    max_wait: int = 10,
) -> Callable:
    """Decorator to retry transient failures with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (default 3).
        initial_wait: Initial wait time in seconds (default 1).
        max_wait: Maximum wait time between retries (default 10).

    Returns:
        Decorator function.

    Example:
        ```python
        @retry_transient(max_attempts=3)
        async def fetch_data():
            return await external_api.get()
        ```

    Behavior:
        - Retries up to max_attempts times
        - Waits 1s, then 2s, then 4s (exponential backoff with jitter)
        - Only retries transient errors (timeouts, connection errors, 429s)
        - Does NOT retry permanent errors (401, 404, 400)
        - Logs each retry attempt
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=initial_wait, max=max_wait),
        retry=retry_if_exception(is_retryable_exception),
        before_sleep=lambda retry_state: logger.warning(
            "Retry attempt %d/%d after error: %s",
            retry_state.attempt_number,
            max_attempts,
            retry_state.outcome.exception(),
        ),
        reraise=True,
    )
