---
status: pending
priority: p3
issue_id: "019"
tags: [code-review, backend, validation]
dependencies: []
---

# Add `validate_not_all_none` to `UserSettingsUpdate`

## Problem Statement

`PeriodLogUpdate` has a `model_validator` that rejects all-`None` payloads. `UserSettingsUpdate` has the same structure but no equivalent guard — a `PATCH /api/users/settings` with an empty body `{}` silently succeeds, writes nothing, and returns the current row. Inconsistent with how `PeriodLogUpdate` is handled in the same branch.

## Findings

- `backend/app/models/users.py` — `UserSettingsUpdate` has no `validate_not_all_none`
- `backend/app/models/period.py` — `PeriodLogUpdate` has it
- Python reviewer flagged as inconsistency

## Proposed Solutions

### Option 1: Add the same validator to `UserSettingsUpdate`

```python
@model_validator(mode="after")
def validate_not_all_none(self) -> "UserSettingsUpdate":
    if all(v is None for v in [self.period_tracking_enabled, self.has_uterus, self.journey_stage]):
        raise ValueError("At least one field must be provided for settings update")
    return self
```

**Effort:** 5 minutes

**Risk:** Low

## Technical Details

**Affected files:**
- `backend/app/models/users.py` — `UserSettingsUpdate`

## Acceptance Criteria

- [ ] `PATCH /api/users/settings` with empty body returns 422
- [ ] Test added: `test_update_settings_when_empty_payload_then_returns_422`

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
