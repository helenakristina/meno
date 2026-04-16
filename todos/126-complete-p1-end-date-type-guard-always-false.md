---
status: complete
priority: p1
issue_id: "126"
tags: [code-review, python, bug, context-builder]
---

# `end_date` type guard always False — sanitization never applied to stopped medications

## Problem Statement

`backend/app/utils/context_builder.py` lines 103–106:

```python
end = (
    sanitize_prompt_input(med.end_date, max_length=50)
    if isinstance(med.end_date, str)
    else med.end_date
)
change_lines.append(f"  - {name} {dose} ({method}), stopped {end}")
```

`MedicationResponse.end_date` is typed as `date | None`. In production it will always be a `date` object, never a `str`. The `isinstance(med.end_date, str)` guard is therefore always `False`, meaning:

1. `sanitize_prompt_input` is never called on `end_date`
2. The raw `date` object is f-string formatted directly into the prompt
3. The `str` branch is dead code

While `date` objects cannot carry injection payloads, the intent was clearly to sanitize and format the value consistently — calling `sanitize_prompt_input(str(med.end_date), max_length=50)` unconditionally is both correct and simpler.

There is no test that exercises the `str` branch because the Pydantic model enforces `date`.

## Proposed Solution

```python
end = sanitize_prompt_input(str(med.end_date), max_length=50)
change_lines.append(f"  - {name} {dose} ({method}), stopped {end}")
```

**Effort:** Trivial  
**Risk:** None — replaces dead-code conditional with unconditional conversion

## Acceptance Criteria

- [ ] `isinstance(med.end_date, str)` guard removed
- [ ] `end_date` is always converted to string and passed through `sanitize_prompt_input`
- [ ] Existing medication tests still pass

## Work Log

- 2026-04-15: Identified by PR #25 code review (kieran-python-reviewer)
