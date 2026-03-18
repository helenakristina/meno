---
status: pending
priority: p2
issue_id: "012"
tags: [code-review, backend, error-handling]
dependencies: []
---

# Wrap `date.fromisoformat` in `get_logs` to return 400 not 500 on bad date params

## Problem Statement

`PeriodService.get_logs()` calls `date.fromisoformat(start_date)` without a try/except. A malformed date like `?start_date=not-a-date` raises a `ValueError` from the stdlib. If the global exception handler in `main.py` doesn't map `ValueError` to a 400, the client receives a 500 with an unhelpful error message instead of a clean 422/400.

## Findings

- `backend/app/services/period.py:81-82` — `date.fromisoformat(start_date) if start_date else None`
- Python reviewer and security sentinel both flagged this
- Not exploitable (can't bypass auth), but produces misleading 500 error UX

## Proposed Solutions

### Option 1: Catch `ValueError` and raise `ValidationError`

**Approach:**
```python
try:
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
except ValueError:
    raise ValidationError("Invalid date format. Use YYYY-MM-DD.")
```

**Pros:** Clean 400 response, uses project's domain exception

**Cons:** None

**Effort:** 10 minutes

**Risk:** Low

---

### Option 2: Move date parsing to route with FastAPI query param type

**Approach:** Change route param from `start_date: str | None` to `start_date: date | None`. FastAPI validates and parses automatically, returning 422 on bad input.

**Pros:** Validation at the HTTP boundary, no service code needed

**Cons:** Requires service signature change to accept `date` objects instead of strings

**Effort:** 20 minutes

**Risk:** Low

## Recommended Action

Option 2 is cleaner — let FastAPI handle the validation at the boundary. Change route query params to `date | None` type and update service signature accordingly.

## Technical Details

**Affected files:**
- `backend/app/api/routes/period.py` — `get_logs` route query param types
- `backend/app/services/period.py:81-82` — remove `fromisoformat` calls

## Acceptance Criteria

- [ ] `GET /api/period/logs?start_date=not-a-date` returns 422, not 500
- [ ] Valid ISO dates still work correctly
- [ ] `GET /api/period/logs` with no params works (None case)

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified unhandled ValueError from stdlib date parsing
- Assessed both fix options
