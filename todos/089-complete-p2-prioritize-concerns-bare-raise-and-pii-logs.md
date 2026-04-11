---
status: pending
priority: p2
issue_id: "089"
tags: [code-review, backend, error-handling, security, logging]
dependencies: []
---

# `prioritize_concerns` bare `raise` + plain `user_id` in log lines

## Problem Statement

Two independent issues in `appointment.py` routes and repository that break established patterns in this codebase.

### Issue A: Bare `raise` in `prioritize_concerns`

`prioritize_concerns` catches `EntityNotFoundError` and `DatabaseError` then does bare `raise`, letting domain exceptions propagate as HTTP 500 with no user-facing message. Every other route in the file converts these to explicit 404/500 HTTPExceptions. The inconsistency means error response shape depends on the global exception handler.

**File**: `backend/app/api/routes/appointment.py`, lines 322–337

### Issue B: Plain `user_id` in repository log lines

`save_context` (line 73) and `get_user_prep_history` (line 808) in the repository log `user_id` in plain text. CLAUDE.md and LOGGING.md require `hash_user_id(user_id)` on all log lines.

**File**: `backend/app/repositories/appointment_repository.py`, lines ~73, ~78, ~808

## Proposed Solution

**Issue A** — follow the pattern from `save_narrative` (lines 192–209):

```python
except (EntityNotFoundError, DatabaseError) as exc:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND if isinstance(exc, EntityNotFoundError)
        else status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    )
```

**Issue B** — swap plain `user_id` for `hash_user_id(user_id)` in the two log call sites.

## Acceptance Criteria

- [ ] `prioritize_concerns` converts `EntityNotFoundError` → 404, `DatabaseError` → 500 with explicit messages
- [ ] `save_context` error and success log lines use `hash_user_id(user_id)`
- [ ] `get_user_prep_history` log lines use `hash_user_id(user_id)`
- [ ] Existing tests for prioritize endpoint still pass
