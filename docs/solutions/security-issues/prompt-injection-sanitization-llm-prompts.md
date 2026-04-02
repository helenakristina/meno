---
title: Prompt Injection Sanitization Pattern for LLM Prompts
category: security-issues
date: 2026-04-01
tags: [security, llm, prompt-injection, sanitization, appointment-prep]
related_issues: []
keywords: [prompt injection, user input validation, LLM safety, sanitization]
severity: critical
---

## Problem

User-generated content (symptom descriptions, concerns, narratives, urgent_symptom) was being directly interpolated into LLM prompts without sanitization, creating **prompt injection vulnerabilities**. Malicious input could:

- Hijack conversation context
- Override system instructions via `system:` marker injection
- Impersonate assistant via `assistant:` marker injection
- Inject XML-like tags to manipulate prompt structure
- Exploit multi-line newlines to break prompt formatting

**Affected code:** `backend/app/llm/appointment_prompts.py` (lines 224-298)

```python
# VULNERABLE: Direct interpolation
urgent_concern = urgent_symptom if urgent_symptom else "not provided"
return (
    f"..."
    f"- Urgent Concern: {urgent_concern}\n"  # User input, unsanitized
    f"- Narrative Summary: {narrative}\n"     # User input, unsanitized
)
```

## Root Cause

No sanitization layer between API input and LLM prompt construction. User content flowed directly from request → prompt builder → LLM, bypassing defense-in-depth validation.

## Solution

Implemented `_sanitize_prompt_input()` helper function that:

1. **Handles empty input**: Returns `"not provided"` for None/empty strings
2. **Enforces max length**: Truncates to 2000 chars (prevents prompt flooding)
3. **Removes injection markers**: Strips `"system:"`, `"user:"`, `"assistant:"`
4. **Strips XML tags**: Removes `<tag>` patterns that could manipulate structure
5. **Normalizes newlines**: Converts `\n` and `\r` to spaces (prevents multi-line injection)
6. **Trims whitespace**: Removes leading/trailing whitespace

### Implementation

**File:** `backend/app/llm/appointment_prompts.py` (lines 28-44)

```python
def _sanitize_prompt_input(text: str | None, max_length: int = 2000) -> str:
    """Sanitize user input before including in LLM prompts.

    Removes prompt injection markers, XML tags, and normalizes whitespace.
    """
    if not text:
        return "not provided"

    text = text[:max_length]
    # Remove potential prompt injection markers
    text = text.replace("system:", "").replace("user:", "").replace("assistant:", "")
    # Strip XML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    # Strip newlines (per Ask Meno v2 learnings)
    text = text.replace("\n", " ").replace("\r", " ")
    return text.strip()
```

### Applied to All Prompt Functions

```python
# build_provider_questions_user_prompt()
user_prompt = build_provider_questions_user_prompt(
    user_context=_sanitize_prompt_input(user_context)
)

# build_scenario_suggestions_user_prompt()
user_prompt = build_scenario_suggestions_user_prompt(
    concerns_text=_sanitize_prompt_input(concerns_text)
)

# build_provider_summary_user_prompt()
user_prompt = build_provider_summary_user_prompt(
    narrative=_sanitize_prompt_input(narrative),
    concerns_text=_sanitize_prompt_input(concerns_text),
    urgent_symptom=_sanitize_prompt_input(urgent_symptom),
)

# build_cheatsheet_user_prompt()
user_prompt = build_cheatsheet_user_prompt(
    narrative=_sanitize_prompt_input(narrative),
    concerns_text=_sanitize_prompt_input(concerns_text),
    urgent_symptom=_sanitize_prompt_input(urgent_symptom),
)
```

## Test Coverage

**File:** `backend/tests/llm/test_appointment_prompts.py`

Created `TestSanitizePromptInput` class with 10 unit tests covering:

- None/empty input handling
- Whitespace trimming
- Newline/carriage return removal
- System/user/assistant prompt marker removal
- XML tag stripping
- Maximum length enforcement
- Field-specific injection attempts (narrative, concerns, urgent_symptom, user_context)

All 67 appointment prompt tests pass. No regressions.

## Prevention Strategies

### For Future LLM Integrations

1. **Always sanitize user input before LLM prompt inclusion** — Apply `_sanitize_prompt_input()` or equivalent at prompt builder layer
2. **Use prompt markers as allowlist** — Only `system:`, `user:`, `assistant:` get special treatment; strip everything else
3. **Test with attack payloads** — Unit tests should include injection attempts like:
   ```python
   "system: override instructions here"
   "<script>alert('xss')</script>"
   "line1\nline2"  # Multi-line injection
   ```
4. **Log safely** — Use `safe_keys()` and `hash_user_id()` from `app.utils.logging` to avoid logging sanitized user content in error messages
5. **Defense in depth** — Sanitize at service layer (business logic), not just at route layer (API boundary)

### Related Security Pattern

For API input validation (appointment_service.py), also implemented `_sanitize_urgent_symptom()`:

```python
def _sanitize_urgent_symptom(self, symptom: str | None) -> str | None:
    """Sanitize urgent_symptom input for keyword matching."""
    if not symptom:
        return None
    symptom = symptom[:200]  # Limit length for DoS prevention
    symptom = re.sub(r'[^\w\s\-(),.]', '', symptom)  # Whitelist allowed chars
    return symptom.strip()
```

## Key Learnings

- **Prompt injection is real** — LLMs are code interpreters; user content is code. Treat it like SQL injection.
- **Newlines are dangerous** — Multi-line injections can break prompt structure. Normalize to spaces.
- **Marker-based attacks work** — LLMs respond to `system:`, `user:`, `assistant:` markers in text. Strip them.
- **XML/HTML tags matter** — Some prompting frameworks use tags for structure. Strip unknown tags.
- **Max length prevents DoS** — Extremely long input can cause timeout or resource exhaustion. Enforce limits.

## Files Modified

- `backend/app/llm/appointment_prompts.py` — Added `_sanitize_prompt_input()`, applied to 4 prompt builder functions
- `backend/tests/llm/test_appointment_prompts.py` — Added 16 new tests (10 sanitization unit tests + 6 field-specific tests)

## Acceptance Criteria

- ✅ Sanitization function added to `appointment_prompts.py`
- ✅ All user-generated content sanitized: `narrative`, `concerns_text`, `urgent_symptom`, `user_context`
- ✅ Unit tests for sanitization function (10 tests)
- ✅ Field-specific injection tests (6 tests)
- ✅ No breaking changes to existing functionality
- ✅ All 67 appointment prompt tests passing

## Reference

**Related institutional knowledge:**

- `docs/solutions/security-issues/ask-meno-v2-review-learnings.md` — Prompt injection prevention patterns from Ask Meno v2

**OWASP Reference:**

- [OWASP Prompt Injection](https://owasp.org/www-community/attacks/Prompt_Injection)
- [CWE-94: Code Injection](https://cwe.mitre.org/data/definitions/94.html)
