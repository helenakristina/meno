---
status: pending
priority: p1
issue_id: "005"
tags: [code-review, backend, security, pii, logging]
dependencies: []
---

# Apply `hash_user_id()` to all log calls in `period_repository.py` and `user_repository.py`

## Problem Statement

`period_repository.py` logs raw `user_id` UUID strings in all 11 log call sites. `user_repository.py` similarly logs raw `user_id` in ~15 call sites, and line 195 logs the user's **email address** in plaintext. This violates the project's PII-safe logging standard (LOGGING.md) and is a HIPAA-relevant risk: if logs are shipped to Railway, Datadog, or Sentry, user UUIDs and emails become linkable to health records.

The `PeriodService` already correctly calls `hash_user_id()` — the repository layer is inconsistent.

## Findings

- `backend/app/repositories/period_repository.py` — lines 67, 73, 109, 136, 166, 205, 211, 234, 240, 269, 293 — raw `user_id` in all log calls
- `backend/app/repositories/user_repository.py` — ~15 log call sites with raw `user_id`
- `backend/app/repositories/user_repository.py:195` — `logger.info("User profile created: id=%s email=%s", user_id, email)` — **email in plaintext**
- `hash_user_id` is in `app.utils.logging` and is already used by `period.py` service
- New methods added in this branch (`get_settings`, `update_settings`) repeat the pattern

## Proposed Solutions

### Option 1: Import `hash_user_id` and apply to all log calls

**Approach:**
1. Add `from app.utils.logging import hash_user_id` to `period_repository.py`
2. Replace all `user_id` log arguments with `hash_user_id(user_id)`
3. Do the same for the new `get_settings` / `update_settings` calls in `user_repository.py`
4. Remove `email` from `user_repository.py:195` log call (or replace with `safe_len(email)`)

```python
# Before
logger.error("DB insert failed for period log user=%s: %s", user_id, exc)

# After
logger.error("DB insert failed for period log user=%s: %s", hash_user_id(user_id), exc)
```

**Pros:** Mechanical fix, consistent with service layer

**Cons:** None

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1. Find-and-replace in both files. Pay particular attention to the email log in `user_repository.py:195`.

## Technical Details

**Affected files:**
- `backend/app/repositories/period_repository.py` — 11 log call sites
- `backend/app/repositories/user_repository.py` — ~15 log call sites + email removal at line 195

## Acceptance Criteria

- [ ] No raw `user_id` in any log statement in `period_repository.py`
- [ ] No raw `user_id` in any log statement in `user_repository.py`
- [ ] Email address removed from `user_repository.py:195` log call
- [ ] `hash_user_id` imported in `period_repository.py`

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified all 11 log sites in period_repository.py
- Identified email plaintext log in user_repository.py:195
- Confirmed hash_user_id already used in service layer (inconsistency)
