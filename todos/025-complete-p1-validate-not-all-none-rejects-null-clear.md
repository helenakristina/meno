---
status: pending
priority: p1
issue_id: "025"
tags: [code-review, pydantic, api-design, backend, logic-error]
dependencies: []
---

# `PeriodLogUpdate` validator rejects valid null-clear PATCH payloads

## Problem Statement

`PeriodLogUpdate.validate_not_all_none` checks `if self.period_end is None and self.flow_level is None and self.notes is None` and raises a ValidationError. But with `model_fields_set` semantics, a client sending `{"notes": null}` to clear notes has all three fields as None — the validator incorrectly rejects it with "At least one field must be provided for update" even though a meaningful field was explicitly provided.

## Findings

- **File**: `backend/app/models/period.py:28-32`
- The validator was written to guard against an empty `{}` payload, but `is None` cannot distinguish "not provided" from "explicitly set to null"
- `model_fields_set` solves this exactly — it is populated at parse time with only fields explicitly present in the input
- Repository already uses `model_fields_set` for conditional writes, so this validator is doubly inconsistent

## Proposed Solution

```python
@model_validator(mode="after")
def validate_not_all_none(self) -> "PeriodLogUpdate":
    if not self.model_fields_set:
        raise ValueError("At least one field must be provided for update")
    return self
```

## Acceptance Criteria
- [ ] Validator uses `model_fields_set`, not None checks
- [ ] Test: `PeriodLogUpdate.model_validate({"notes": None})` succeeds (notes in model_fields_set)
- [ ] Test: `PeriodLogUpdate.model_validate({})` raises ValueError
