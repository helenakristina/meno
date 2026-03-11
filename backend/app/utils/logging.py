"""Logging utilities for safe, PII-free logging.

For a health app, logs must never contain:
- Symptom descriptions or medical data
- User-generated free-text entries
- Personal health information (age, dates of birth, etc.)
- Even brief snippets or previews of sensitive data

This module provides utilities to log safely while preserving debuggability.
"""

import logging
from typing import Any, Optional
import hashlib

logger = logging.getLogger(__name__)


def hash_user_id(user_id: str, prefix: str = "user_") -> str:
    """Hash a user ID for safe logging.

    User IDs should never appear in plaintext in logs.
    Instead, log a hash that's consistent per user but doesn't reveal identity.

    Args:
        user_id: User ID (UUID or email).
        prefix: Prefix for the hash (default "user_").

    Returns:
        Hashed user ID like "user_a3f2b1cd..." (first 8 chars of hash).

    Example:
        >>> hash_user_id("550e8400-e29b-41d4-a716-446655440000")
        "user_a3f2b1cd"
    """
    hash_obj = hashlib.sha256(user_id.encode())
    hash_str = hash_obj.hexdigest()[:8]
    return f"{prefix}{hash_str}"


def hash_appointment_id(appointment_id: str) -> str:
    """Hash an appointment ID for safe logging."""
    return hash_user_id(appointment_id, prefix="appt_")


def safe_len(data: Any) -> int:
    """Get length of data without logging the data itself.

    Useful for logging "processed 500 characters" without logging the characters.

    Args:
        data: String or bytes to measure.

    Returns:
        Length of data.

    Example:
        >>> logger.debug("Processing request with %d bytes", safe_len(request_body))
        # Safe: Only logs the length, not the content
    """
    try:
        return len(data)
    except (TypeError, AttributeError):
        return 0


def safe_type(data: Any) -> str:
    """Get type name of data for logging without revealing content.

    Useful for logging "received dict" or "received list" without revealing keys/values.

    Args:
        data: Object to describe.

    Returns:
        Type name like "dict", "list", "str".

    Example:
        >>> logger.debug("Response type: %s", safe_type(response))
        # Logs: "Response type: dict" (not the contents)
    """
    return type(data).__name__


def safe_keys(data: dict) -> str:
    """Get dict keys for logging without revealing values.

    Useful for logging structure without exposing sensitive content.

    Args:
        data: Dictionary to describe.

    Returns:
        Comma-separated key names like "id, name, age".

    Example:
        >>> logger.debug("Response keys: %s", safe_keys(response))
        # Logs: "Response keys: id, name, timestamp" (not values)
    """
    if not isinstance(data, dict):
        return "not a dict"
    return ", ".join(data.keys())


def safe_summary(
    operation: str,
    status: str,
    count: Optional[int] = None,
    duration_ms: Optional[float] = None,
) -> str:
    """Create a safe log message summarizing an operation.

    Use this for logging operation results without exposing data.

    Args:
        operation: What was done ("fetch user context", "generate narrative", etc.)
        status: Result ("success", "error", "timeout", etc.)
        count: Optional count of items processed.
        duration_ms: Optional duration in milliseconds.

    Returns:
        Safe log message.

    Example:
        >>> msg = safe_summary("fetch logs", "success", count=47, duration_ms=123.5)
        >>> logger.info(msg)
        # Logs: "fetch logs: success (47 items, 123.5ms)"
    """
    parts = [f"{operation}: {status}"]

    if count is not None:
        parts.append(f"{count} items")

    if duration_ms is not None:
        parts.append(f"{duration_ms:.1f}ms")

    details = ", ".join(parts[1:])
    if details:
        return f"{parts[0]} ({details})"
    return parts[0]
