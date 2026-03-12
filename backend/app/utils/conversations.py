"""Utilities for conversation processing.

Pure functions for conversation title extraction and message processing.
"""

TITLE_MAX_CHARS = 50


def build_conversation_title(messages: list[dict]) -> str:
    """Extract a display title from conversation messages.

    Scans for the first user message and extracts the first 50 characters.
    Falls back to "New conversation" if no user message exists or if empty.

    Args:
        messages: List of message dicts (role + content).

    Returns:
        Display title string (max 50 chars).

    Example:
        >>> messages = [
        ...     {"role": "user", "content": "What causes brain fog?"},
        ...     {"role": "assistant", "content": "Brain fog during..."}
        ... ]
        >>> build_conversation_title(messages)
        'What causes brain fog?'
    """
    first_user = next((m for m in messages if m.get("role") == "user"), None)
    if not first_user:
        return "New conversation"

    content = (first_user.get("content") or "").strip()
    if not content:
        return "New conversation"

    return content[:TITLE_MAX_CHARS].rstrip()
