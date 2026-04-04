---
status: pending
priority: p2
issue_id: "092"
tags: [code-review, backend, database, correctness]
dependencies: []
---

# `get_latest` join query omits new qualitative context columns

## Problem Statement

`get_latest` in `appointment_repository.py` joins `appointment_prep_contexts` but only selects `appointment_type, goal, dismissed_before, urgent_symptom, created_at`. The four new qualitative context columns (`what_have_you_tried`, `specific_ask`, `history_clotting_risk`, `history_breast_cancer`) added in Phase 5 are not included. Any caller that uses `get_latest` to resume or reconstruct an appointment context will get `None` for all four fields, silently.

## Findings

- **File**: `backend/app/repositories/appointment_repository.py`, line ~293
- `get_latest` is used to retrieve the most recent appointment context (e.g., for history/resume flows)
- The result is deserialized into `AppointmentContext`, which now has these four fields as optional — so no crash, just silent null values

## Proposed Solution

Add the four new columns to the join select string:

```python
"*, appointment_prep_contexts(appointment_type, goal, dismissed_before, "
"urgent_symptom, what_have_you_tried, specific_ask, "
"history_clotting_risk, history_breast_cancer, created_at)"
```

## Acceptance Criteria

- [ ] `get_latest` select includes all four new qualitative context column names
- [ ] Test: `get_latest` with a row that has qualitative context set returns those values (not None)
- [ ] Existing `get_latest` tests still pass
