"""Tests for retry utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.utils.retry import retry_transient, is_retryable_exception


class TestIsRetryableException:
    """Test exception classification."""

    def test_timeout_is_retryable(self):
        """TimeoutError should be retryable."""
        assert is_retryable_exception(TimeoutError("timeout"))

    def test_connection_error_is_retryable(self):
        """ConnectionError should be retryable."""
        assert is_retryable_exception(ConnectionError("connection failed"))

    def test_os_error_is_retryable(self):
        """OSError (network errors) should be retryable."""
        assert is_retryable_exception(OSError("network error"))

    def test_rate_limit_429_is_retryable(self):
        """HTTP 429 (rate limit) should be retryable."""
        exc = MagicMock()
        exc.status_code = 429
        assert is_retryable_exception(exc)

    def test_connection_string_in_exception_is_retryable(self):
        """Exception with 'Connection' in message should be retryable."""
        assert is_retryable_exception(Exception("Connection reset by peer"))

    def test_timeout_string_in_exception_is_retryable(self):
        """Exception with 'timeout' in message should be retryable."""
        assert is_retryable_exception(Exception("Request timeout"))

    def test_auth_401_is_not_retryable(self):
        """HTTP 401 (unauthorized) should NOT be retryable."""
        exc = MagicMock()
        exc.status_code = 401
        assert not is_retryable_exception(exc)

    def test_forbidden_403_is_not_retryable(self):
        """HTTP 403 (forbidden) should NOT be retryable."""
        exc = MagicMock()
        exc.status_code = 403
        assert not is_retryable_exception(exc)

    def test_not_found_404_is_not_retryable(self):
        """HTTP 404 (not found) should NOT be retryable."""
        exc = MagicMock()
        exc.status_code = 404
        assert not is_retryable_exception(exc)

    def test_bad_request_400_is_not_retryable(self):
        """HTTP 400 (bad request) should NOT be retryable."""
        exc = MagicMock()
        exc.status_code = 400
        assert not is_retryable_exception(exc)

    def test_other_exceptions_are_not_retryable(self):
        """Generic exceptions should NOT be retryable."""
        assert not is_retryable_exception(ValueError("invalid input"))
        assert not is_retryable_exception(RuntimeError("generic error"))


class TestRetryTransientDecorator:
    """Test retry decorator behavior."""

    @pytest.mark.asyncio()
    async def test_succeeds_on_first_attempt(self):
        """Test successful call on first attempt (no retry needed)."""

        @retry_transient(max_attempts=3)
        async def func():
            return "success"

        result = await func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        """Test retry succeeds on second attempt."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timeout")
            return "success"

        result = await func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_on_third_attempt(self):
        """Test retry succeeds on third attempt."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"

        result = await func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_all_retries_exhausted(self):
        """Test that exception is raised after all retries exhausted."""

        @retry_transient(max_attempts=2)
        async def func():
            raise TimeoutError("timeout")

        with pytest.raises(TimeoutError):
            await func()

    @pytest.mark.asyncio
    async def test_does_not_retry_permanent_error(self):
        """Test that permanent errors (401) are not retried."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            exc = Exception("Unauthorized")
            exc.status_code = 401  # type: ignore
            raise exc

        with pytest.raises(Exception):
            await func()

        # Should only be called once (no retry on 401)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_does_not_retry_404(self):
        """Test that 404 errors are not retried."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            exc = Exception("Not found")
            exc.status_code = 404  # type: ignore
            raise exc

        with pytest.raises(Exception):
            await func()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_429(self):
        """Test that 429 (rate limit) errors are retried."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = Exception("Rate limit exceeded")
                exc.status_code = 429  # type: ignore
                raise exc
            return "success"

        result = await func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        """Test that ConnectionError is retried."""
        call_count = 0

        @retry_transient(max_attempts=3)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("connection failed")
            return "success"

        result = await func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_custom_max_attempts(self):
        """Test decorator with custom max_attempts."""
        call_count = 0

        @retry_transient(max_attempts=2)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"

        with pytest.raises(TimeoutError):
            await func()

        # Should try twice, not three times
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorated_function_preserves_signature(self):
        """Test that decorator preserves function signature for introspection."""

        @retry_transient(max_attempts=3)
        async def my_function(arg1: str, arg2: int) -> str:
            """My docstring."""
            return f"{arg1}:{arg2}"

        # Should work normally
        result = await my_function("test", 42)
        assert result == "test:42"
