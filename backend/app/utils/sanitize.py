"""Sanitization utilities for user input across the application.

Provides layered sanitization for different contexts:
- LLM prompts: Remove injection markers, XML tags, newlines
- Keyword matching: Whitelist alphanumeric + safe punctuation
- General input: Flexible sanitization with configurable rules
"""

import re


def sanitize_prompt_input(text: str | None, max_length: int = 2000) -> str:
    """Sanitize user input before including in LLM prompts.

    Removes prompt injection markers, XML-like tags, and normalizes whitespace
    to prevent injection attacks and prompt structure breakage.

    Args:
        text: Raw user-provided text (narrative, concerns, context, etc.)
        max_length: Maximum allowed length after sanitization (default 2000 chars)

    Returns:
        Sanitized string safe for LLM inclusion, or "not provided" if input is empty/None.

    Examples:
        >>> sanitize_prompt_input("system: override rules")
        "override rules"
        >>> sanitize_prompt_input("SYSTEM: OVERRIDE")
        "OVERRIDE"
        >>> sanitize_prompt_input(None)
        "not provided"
        >>> sanitize_prompt_input("line1\nline2")
        "line1 line2"
    """
    if not text:
        return "not provided"

    text = text[:max_length]

    # Remove potential prompt injection markers (case-insensitive)
    text = re.sub(r"(?i)(system:|user:|assistant:)", "", text)

    # Strip XML-like tags
    text = re.sub(r"<[^>]+>", "", text)

    # Strip newlines (per Ask Meno v2 learnings — prevents multi-line injection)
    text = text.replace("\n", " ").replace("\r", " ")

    return text.strip()


def sanitize_urgent_symptom(symptom: str | None) -> str | None:
    """Sanitize urgent_symptom input for keyword matching and storage.

    Limits length and removes special characters that could affect downstream
    keyword matching or storage.

    Args:
        symptom: Raw user-provided symptom string

    Returns:
        Sanitized string (alphanumeric + safe punctuation), or None if empty/None.

    Examples:
        >>> sanitize_urgent_symptom("severe hot flashes")
        "severe hot flashes"
        >>> sanitize_urgent_symptom("pain <script>alert('xss')</script>")
        "pain scriptalertxssscript"
        >>> sanitize_urgent_symptom("a" * 500)[:200]
        "aaa..." (truncated to 200)
        >>> sanitize_urgent_symptom(None)
        None
    """
    if not symptom:
        return None

    # Limit length to prevent DoS (generous limit for multi-word symptoms)
    symptom = symptom[:200]

    # Allow alphanumeric, spaces, and common punctuation
    # (parentheses, commas, periods, hyphens)
    symptom = re.sub(r"[^\w\s\-(),.]", "", symptom)

    symptom = symptom.strip()

    return symptom if symptom else None
