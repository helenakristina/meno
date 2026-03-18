---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, backend, api-design]
dependencies: []
---

# Fix `update_log` to allow clearing optional fields via `model_fields_set`

## Problem Statement

`period_repository.update_log()` skips fields with `None` values to support partial updates. But this makes it impossible to **clear** `notes`, `period_end`, or `flow_level` — sending `{"notes": null}` is silently ignored. There's no way to distinguish "field not provided" from "user wants to clear this field." This is the classic PATCH ambiguity problem.

## Findings

- `backend/app/repositories/period_repository.py:188-196` — `if data.notes is not None: update_data["notes"] = data.notes`
- Same pattern for `period_end` and `flow_level`
- `PeriodLogUpdate.validate_not_all_none` already guards against empty payloads
- Pydantic v2 provides `model_fields_set` to check which fields were explicitly set

## Proposed Solutions

### Option 1: Use `model_fields_set` to check explicit inclusion

**Approach:**
```python
if "notes" in data.model_fields_set:
    update_data["notes"] = data.notes  # None means "clear it"
if "period_end" in data.model_fields_set:
    update_data["period_end"] = data.period_end
if "flow_level" in data.model_fields_set:
    update_data["flow_level"] = data.flow_level
```

**Pros:** Standard Pydantic v2 approach, allows explicit null to clear, preserves partial update semantics

**Cons:** None

**Effort:** 15 minutes

**Risk:** Low

## Recommended Action

Option 1. Replace `is not None` checks with `in data.model_fields_set` checks throughout `update_log`.

## Technical Details

**Affected files:**
- `backend/app/repositories/period_repository.py:188-196` — `update_log` method

**Tests to add/update:**
- `test_update_log_when_notes_set_to_null_then_clears_notes`
- `test_update_log_when_notes_omitted_then_leaves_unchanged`

## Acceptance Criteria

- [ ] `PATCH /api/period/logs/{id}` with `{"notes": null}` clears the notes field
- [ ] `PATCH /api/period/logs/{id}` with no `notes` key leaves notes unchanged
- [ ] Same behaviour for `period_end` and `flow_level`
- [ ] Tests cover both "clear" and "omit" cases

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified None-skip pattern preventing field clearing
- Confirmed Pydantic v2 model_fields_set is the standard fix
