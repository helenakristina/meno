---
status: pending
priority: p1
issue_id: "027"
tags: [code-review, database, migration, data-integrity]
dependencies: []
---

# No unique constraint on `(user_id, period_start)` — duplicate dates corrupt cycle calculations

## Problem Statement

The `period_logs` migration has no uniqueness constraint on `(user_id, period_start)`. Two logs on the same start date would cause `_refresh_cycle_analysis` to compute a `cycle_length` of 0 (same date), which is silently dropped by the `if delta > 0` guard — but the second log still exists and would skew analysis. The cycle analysis algorithm assumes each period_start is unique per user.

## Findings

- **File**: `backend/migrations/add_period_tracking.sql`
- `_refresh_cycle_analysis` in `period.py` iterates consecutive logs and depends on ascending unique dates
- A duplicate date produces `delta = 0` which is silently filtered but the duplicate log persists

## Proposed Solution

Add to migration:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_period_logs_user_start
  ON period_logs (user_id, period_start);
```

And add guard in `create_log`:
```python
# Before inserting, check for duplicate start date
# Or rely on the DB unique constraint and catch the error as ValidationError
```

## Acceptance Criteria
- [ ] DB unique constraint on `(user_id, period_start)`
- [ ] `create_log` handles duplicate start date with a meaningful error (400 not 500)
