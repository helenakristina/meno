---
status: complete
priority: p2
issue_id: "051"
tags: [code-review, backend, medications, pydantic, pr-2]
dependencies: []
---

# `MedicationUpdate` PATCH should use `model_fields_set` for null-clearing fields

## Problem Statement

`MedicationRepository.update` likely uses `if value is not None` to build the update dict for optional fields. This means explicitly nulling a field (e.g., clearing `end_date` to re-activate a medication, or clearing `notes`) will be silently dropped. This is a known project pattern from `docs/solutions/`.

## Findings

- `backend/app/repositories/medication_repository.py` — update method
- `backend/app/models/medications.py` — `MedicationUpdate` model has optional fields: `end_date`, `notes`, `dose`, `delivery_method`, `frequency`
- Known learnings pattern: `docs/solutions/logic-errors/pydantic-model-fields-set-patch-semantics.md`
- The fix is to use `"field_name" in data.model_fields_set` instead of `if data.field is not None`
- Per the learnings doc: "Send `{"notes": null}` and assert the null is saved, not dropped"

## Proposed Solutions

### Option 1: Use `model_fields_set` in the repository update (Recommended)

```python
update_data = {}
for field in medication_update.model_fields_set:
    update_data[field] = getattr(medication_update, field)
```

Or equivalently:
```python
update_data = {
    k: v
    for k, v in medication_update.model_dump(exclude_unset=True).items()
}
```

`exclude_unset=True` on `model_dump()` respects `model_fields_set` automatically.

**Pros:** `{"end_date": null}` correctly clears the field, enabling medication re-activation
**Effort:** Small
**Risk:** None

## Recommended Action

Option 1 using `model_dump(exclude_unset=True)` — this is the canonical Pydantic v2 pattern for PATCH.

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py` — update method

**Test to add:**
```python
def test_update_when_end_date_is_none_then_clears_end_date():
    # Send {"end_date": null} → assert end_date IS NULL in DB call
```

## Acceptance Criteria

- [ ] `PATCH /api/medications/{id}` with `{"end_date": null}` saves null (re-activates medication)
- [ ] `PATCH /api/medications/{id}` with `{"notes": null}` saves null (clears notes)
- [ ] Fields omitted from the payload are not included in the DB update
- [ ] Test added for the null-clear case

## Work Log

- 2026-03-18: Identified by learnings-researcher (known pattern `pydantic-model-fields-set-patch-semantics.md`) in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
