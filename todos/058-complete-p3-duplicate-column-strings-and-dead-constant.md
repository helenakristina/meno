---
status: complete
priority: p3
issue_id: "058"
tags: [code-review, backend, medications, cleanup, simplicity, pr-2]
dependencies: []
---

# Duplicated select column strings (6×) and dead `_SPARSE_THRESHOLD_DAYS` constant

## Problem Statement

The full medication column list is copy-pasted verbatim 6 times in `medication_repository.py`. A module-level constant would make field additions a one-line change. Also, `_SPARSE_THRESHOLD_DAYS = 14` is defined in the repository but never used there — only the service uses this constant (as `_SPARSE_LOG_THRESHOLD`).

## Findings

- `backend/app/repositories/medication_repository.py` lines 154, 184, 386, 421, 429, 468 — identical select string repeated 6×
- `backend/app/repositories/medication_repository.py` line 28 — `_SPARSE_THRESHOLD_DAYS = 14` defined but never referenced in the file
- `backend/app/services/medication.py` line 32 — `_SPARSE_LOG_THRESHOLD = 14` is the same value used in the service
- Identified by code-simplicity-reviewer

## Proposed Solutions

### Option 1: Extract column constant and remove dead constant (Recommended)

```python
# At module top
_MED_COLS = "id, medication_ref_id, medication_name, dose, delivery_method, frequency, start_date, end_date, previous_entry_id, notes"
_REF_COLS = "id, brand_name, generic_name, hormone_type, common_forms, common_doses, notes, is_user_created"
```

Replace all 6 inline strings with `_MED_COLS`. Remove `_SPARSE_THRESHOLD_DAYS` from the repository.

**Effort:** Small
**Risk:** None

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py`

## Acceptance Criteria

- [ ] Select column string extracted to `_MED_COLS` constant
- [ ] `_SPARSE_THRESHOLD_DAYS` removed from repository
- [ ] All tests still pass

## Work Log

- 2026-03-18: Identified by code-simplicity-reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
