---
status: pending
priority: p3
issue_id: "018"
tags: [code-review, backend, data-integrity]
dependencies: []
---

# Fix `calculated_at` not refreshed on cycle analysis upsert + `UserSettingsResponse` model_config

## Problem Statement

Two small backend model/repository issues:

1. **`calculated_at` not refreshed on upsert**: `period_repository.upsert_cycle_analysis()` never sets `calculated_at` in the upsert payload. The DB sets it on INSERT via `DEFAULT NOW()`, but subsequent upserts don't update it. The `calculated_at` field in the response will be stale after the first upsert.

2. **`UserSettingsResponse` missing `model_config`**: `UserProfile` and `UserResponse` both have `model_config = {"from_attributes": True}`. `UserSettingsResponse` does not. Currently constructed manually from `row.get(...)` so no runtime error, but inconsistent and fragile if construction pattern changes.

## Findings

- `backend/app/repositories/period_repository.py:248-267` — upsert payload never sets `calculated_at`
- `backend/app/models/users.py` — `UserSettingsResponse` lacks `model_config = {"from_attributes": True}`
- Python reviewer flagged both

## Proposed Solutions

### Option 1: Fix both in one pass

1. Add `"calculated_at": datetime.utcnow().isoformat()` to the upsert dict in `upsert_cycle_analysis`
2. Add `model_config = {"from_attributes": True}` to `UserSettingsResponse`

**Effort:** 10 minutes

**Risk:** Low

## Technical Details

**Affected files:**
- `backend/app/repositories/period_repository.py:248-267`
- `backend/app/models/users.py` — `UserSettingsResponse`

## Acceptance Criteria

- [ ] `calculated_at` is updated on every cycle analysis upsert
- [ ] `UserSettingsResponse.model_config = {"from_attributes": True}` added

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
