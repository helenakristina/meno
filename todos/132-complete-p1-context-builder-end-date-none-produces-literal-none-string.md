---
status: pending
priority: p1
issue_id: "132"
tags: [code-review, python, bug, context-builder, llm-safety]
dependencies: ["126"]
---

# `str(med.end_date)` sends literal `"None"` to LLM when `end_date` is absent

## Problem Statement

`backend/app/utils/context_builder.py` line 90:

```python
end = sanitize_prompt_input(str(med.end_date), max_length=50)
change_lines.append(f"  - {name} {dose} ({method}), stopped {end}")
```

`MedicationResponse.end_date` is typed `date | None`. When `end_date` is `None`, `str(None)` produces the string `"None"`. `sanitize_prompt_input` only returns `"not provided"` when its input is falsy — the string `"None"` is truthy, so it passes through. The LLM receives `"stopped None"` which is nonsensical and could confuse its response.

**Note:** Todo #126 fixed the original `isinstance(med.end_date, str)` guard (which was always False). It replaced it with `sanitize_prompt_input(str(med.end_date), max_length=50)` — which is simpler but still doesn't guard against `None`. This is a second-order bug that #126 didn't catch.

In practice `recent_changes` are medications the user stopped, so most will have an end_date. But `date | None` in the model means None is a valid state, and there's no test covering it.

## Proposed Solution

**Option A — Guard before converting:**

```python
end = sanitize_prompt_input(
    str(med.end_date) if med.end_date else "date unknown",
    max_length=50,
)
```

**Option B — Use `sanitize_prompt_input` fallback behavior:**

Pass `None` directly to `sanitize_prompt_input` — it returns `"not provided"` for falsy inputs. But `sanitize_prompt_input` expects `str`, not `None`, so this requires checking the function signature first.

**Recommended:** Option A. Explicit, readable, correct.

**Effort:** Trivial  
**Risk:** None — only affects the string rendered in the prompt for stopped medications with no end_date

## Acceptance Criteria

- [ ] When `med.end_date` is `None`, the prompt renders `"stopped date unknown"` (or equivalent), not `"stopped None"`
- [ ] Add test case in `TestMedicationBlock` with `end_date=None` in a `recent_changes` entry
- [ ] Existing medication tests still pass

## Work Log

- 2026-04-21: Identified by PR #25 code review (kieran-python-reviewer). Extends todo #126 — the isinstance-guard fix introduced this edge case.
