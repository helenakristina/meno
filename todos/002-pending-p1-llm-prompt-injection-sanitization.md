---
name: LLM Prompt Injection Risk - User Content Sanitization
status: complete
priority: p1
tags: [code-review, security, llm]
dependencies: []
---

## Problem Statement

User-generated content (symptom descriptions, concerns, narratives, urgent_symptom) is directly interpolated into LLM prompts without sanitization, creating prompt injection vulnerabilities.

## Findings

**From:** security-sentinel, learnings-researcher (citing Ask Meno v2 learnings)

**Severity:** IMPORTANT (could lead to prompt hijacking)

**Vulnerable locations:**

1. `backend/app/llm/appointment_prompts.py` lines 224-255 (`build_provider_summary_user_prompt`)
2. `backend/app/llm/appointment_prompts.py` lines 258-298 (`build_cheatsheet_user_prompt`)

**Example vulnerable code:**

```python
# Lines 237-248 in appointment_prompts.py
urgent_concern = urgent_symptom if urgent_symptom else "not provided"
return (
    f"..."
    f"- Urgent Concern: {urgent_concern}\n"  # User content
    f"- Narrative Summary: {narrative}\n"   # User content
    f"- Concerns List: {concerns_text}\n"   # User content
```

**Risk:** Malicious input could:

- Hijack conversation context
- Override system instructions
- Extract or manipulate prompt structure

## Proposed Solutions

### Option A: Add Sanitization Helper (Recommended)

**Effort:** Small
**Risk:** Low

Add a sanitization function and apply to all user inputs:

```python
def _sanitize_prompt_input(text: str | None, max_length: int = 2000) -> str:
    """Sanitize user input before including in LLM prompts."""
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

Then wrap all user inputs:

```python
user_prompt = build_provider_summary_user_prompt(
    narrative=_sanitize_prompt_input(narrative),
    concerns_text=_sanitize_prompt_input(concerns_text),
    urgent_symptom=_sanitize_prompt_input(urgent_symptom),
    ...
)
```

### Option B: Use Structured Input Validation

**Effort:** Medium
Validate inputs at the API layer using Pydantic validators before they reach prompt builders.

## Recommended Action

Implement Option A before merge. This follows the pattern established in Ask Meno v2 (see docs/solutions/security-issues/ask-meno-v2-review-learnings.md Lesson #2).

## Technical Details

**Affected files:**

- `backend/app/llm/appointment_prompts.py`
- `backend/app/services/appointment.py` (for scenario selection input)

**Related institutional knowledge:**

- docs/solutions/security-issues/ask-meno-v2-review-learnings.md (Prompt Injection Prevention)

## Acceptance Criteria

- [ ] Sanitization function added to `appointment_prompts.py`
- [ ] All user-generated content sanitized before prompt inclusion:
  - [ ] `narrative` parameter
  - [ ] `concerns_text` parameter
  - [ ] `urgent_symptom` parameter
  - [ ] `urgent_concern` parameter
- [ ] Unit tests for sanitization function
- [ ] No breaking changes to existing functionality

## Work Log

| Date       | Action                      | Result  |
| ---------- | --------------------------- | ------- |
| 2026-03-31 | Created from security audit | Pending |
