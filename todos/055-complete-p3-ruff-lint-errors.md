---
status: complete
priority: p3
issue_id: "055"
tags: [code-review, backend, lint, pr-2]
dependencies: []
---

# 6 ruff lint errors in changed files — all auto-fixable

## Problem Statement

Six ruff lint errors exist across `dependencies.py`, `main.py`, and `ask_meno.py`. All are auto-fixable with `ruff check --fix`.

## Findings

- `backend/app/api/dependencies.py` — bare `f` prefix on non-interpolated string
- `backend/app/main.py` — `MenoBaseError` imported but unused
- `backend/app/services/ask_meno.py` lines 17, 29, 33, 35 — `re`, `Citation`, `StructuredClaim`, `StructuredSection` imported but unused
- Identified by Python reviewer

## Proposed Solutions

### Option 1: Run `ruff check --fix` (Recommended)

```bash
cd backend && uv run ruff check --fix app/api/dependencies.py app/main.py app/services/ask_meno.py
```

**Effort:** Tiny
**Risk:** None — unused imports only

## Recommended Action

Run the command above and commit the fixes.

## Technical Details

**Affected files:**
- `backend/app/api/dependencies.py`
- `backend/app/main.py`
- `backend/app/services/ask_meno.py`

## Acceptance Criteria

- [ ] `uv run ruff check .` exits with 0 errors in changed files

## Work Log

- 2026-03-18: Identified by Python reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
