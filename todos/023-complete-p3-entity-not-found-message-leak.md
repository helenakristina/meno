---
status: pending
priority: p3
issue_id: "023"
tags: [code-review, backend, security, hardening]
dependencies: []
---

# Harden `EntityNotFoundError` handler to return generic "Not found" message

## Problem Statement

`main.py`'s `entity_not_found_handler` returns `{"detail": str(exc)}` — the full exception message (e.g., `"Period log not found"`). This is a minor information oracle: an attacker probing UUID-space with a stolen JWT gets a reliable `"Period log not found"` response confirming the ID doesn't belong to them (vs. belonging to another user). Standard practice is to return a fixed `"Not found"` string regardless of the specific resource type.

## Findings

- `backend/app/main.py` entity_not_found_handler — returns `{"detail": str(exc)}`
- `period_repository.py` — raises `EntityNotFoundError("Period log not found")`
- `user_repository.py` — raises `EntityNotFoundError("User not found")`
- Security sentinel flagged as Low-Medium

## Proposed Solutions

### Option 1: Return fixed string in the exception handler

```python
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(status_code=404, content={"detail": "Not found"})
```

**Effort:** 2 minutes

**Risk:** None (only changes response body wording)

## Technical Details

**Affected files:**
- `backend/app/main.py` — `entity_not_found_handler`

## Acceptance Criteria

- [ ] All 404 responses return `{"detail": "Not found"}` regardless of resource type
- [ ] Internal exception messages are still descriptive (for logging/debugging purposes)

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
