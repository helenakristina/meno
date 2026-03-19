---
status: complete
priority: p2
issue_id: "044"
tags: [code-review, backend, medications, cleanup, pr-2]
dependencies: []
---

# `_invalidate_summary_cache` is a no-op scheduled 4× per mutation — delete or stub clearly

## Problem Statement

`_invalidate_summary_cache` contains only a `logger.info` call and no actual work. It is scheduled with `asyncio.ensure_future` on every mutating operation (create, update, change_dose, delete). Operators will see "cache invalidation triggered" log lines that have no corresponding effect. Future developers will assume cache invalidation is wired when it is not.

## Findings

- `backend/app/services/medication.py` lines 308–327 — method body is a `try/except` around a single `logger.info`
- Called with `asyncio.ensure_future` at lines 99, 113, 140, 149
- `asyncio.ensure_future` is also the wrong API — `asyncio.create_task` is preferred in modern Python; tasks scheduled with `ensure_future` are silently dropped on event loop shutdown
- Comment says "cache regeneration handled by next call to get_summary" — but no mechanism detects staleness caused by medication changes
- Identified by Python reviewer, architecture-strategist, and code-simplicity-reviewer (all independently)

## Proposed Solutions

### Option 1: Delete the method and all four call sites (Recommended)

Remove `_invalidate_summary_cache`, the four `asyncio.ensure_future(...)` lines, and any related imports.

**Pros:** Zero misleading signal, zero fire-and-forget overhead, codebase says what it does
**Effort:** Small (delete 24 lines + 4 call sites)
**Risk:** None — method does nothing today

### Option 2: Keep as a clearly-labelled stub

Replace the method body with a `pass` and a prominent `# TODO:` comment. Remove the `asyncio.ensure_future` calls — a no-op doesn't need to be async.

**Pros:** Documents the intent for future implementation
**Cons:** Still dead code, just honestly named
**Effort:** Small

## Recommended Action

Option 1 — dead code that pretends to work is worse than no code at all. Document the intent in a comment near the write methods if needed.

## Technical Details

**Affected files:**
- `backend/app/services/medication.py` lines 99, 113, 140, 149 (call sites)
- `backend/app/services/medication.py` lines 308–327 (method)
- `backend/tests/services/test_medication_service.py` (remove any tests for this method)

## Acceptance Criteria

- [ ] `_invalidate_summary_cache` and all four call sites are removed
- [ ] No `asyncio.ensure_future` calls remain in `medication.py`
- [ ] All 61 existing tests still pass

## Work Log

- 2026-03-18: Identified by Python reviewer, architecture-strategist, code-simplicity-reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
