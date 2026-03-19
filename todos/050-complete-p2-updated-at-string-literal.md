---
status: complete
priority: p2
issue_id: "050"
tags: [code-review, backend, medications, bug, pr-2]
dependencies: []
---

# `updated_at = "now()"` passes a string literal — column set to text, not current timestamp

## Problem Statement

`MedicationRepository.update` sets `update_data["updated_at"] = "now()"`. Supabase's Python client treats this as a plain string value — the column will be set to the literal text `"now()"` rather than the current timestamp. The same pattern exists in `period_repository.py` (pre-existing bug).

## Findings

- `backend/app/repositories/medication_repository.py` line 266
- PostgREST/Supabase client does not interpret `"now()"` as a SQL expression
- The `updated_at TIMESTAMPTZ` column will contain the string `"now()"` which Postgres will reject with a type error (or silently coerce depending on driver version)
- Pre-existing pattern in `period_repository.py` — should be fixed both places

## Proposed Solutions

### Option 1: Use Python `datetime` (Recommended)

```python
from datetime import datetime, timezone
update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
```

**Pros:** Correct timestamp, no DB error
**Effort:** Tiny
**Risk:** None

### Option 2: Remove `updated_at` from the update dict, rely on DB trigger

Add a `BEFORE UPDATE` trigger on `user_medications` that sets `updated_at = NOW()` automatically. Then remove the explicit assignment from the repository.

**Pros:** Timestamp is always correct, can't be spoofed from application layer
**Effort:** Small — requires migration update
**Risk:** Requires migration addition

## Recommended Action

Option 1 as immediate fix. Option 2 is the cleaner long-term pattern but requires a migration. Also fix the same issue in `period_repository.py`.

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py` line 266
- `backend/app/repositories/period_repository.py` (same pre-existing pattern)

## Acceptance Criteria

- [ ] `updated_at` is set to a valid `datetime.now(timezone.utc).isoformat()` value
- [ ] `user_medications` rows show correct `updated_at` timestamps after updates

## Work Log

- 2026-03-18: Identified by architecture-strategist in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
