---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, backend, architecture, yagni]
dependencies: [004]
---

# Delete `PeriodServiceBase` ABC — unused, not wired in DI, YAGNI violation

## Problem Statement

`period_base.py` defines a `PeriodServiceBase` ABC with 6 abstract methods mirroring `PeriodService` 1:1. It is never referenced in `dependencies.py` (the DI wiring uses the concrete `PeriodService` type directly) and there is no alternate implementation. The ABC adds 40+ lines of parallel boilerplate with zero runtime benefit. Per CLAUDE.md: use ABC when you have (or imminently need) multiple implementations.

## Findings

- `backend/app/services/period_base.py` — 40-line ABC, 6 abstract methods
- `backend/app/api/dependencies.py` — `get_period_service` returns `PeriodService` (concrete type), not `PeriodServiceBase`
- `backend/app/api/routes/period.py` — all 5 route handlers type-hint `service: PeriodService`, not `PeriodServiceBase`
- Compare: `LLMProvider` ABC IS worth keeping — has two real implementations (`OpenAIProvider`, mock), wired via `LLM_PROVIDER` env var
- Code simplicity reviewer and architecture reviewer both flagged this

## Proposed Solutions

### Option 1: Delete `period_base.py`

**Approach:**
1. Delete `backend/app/services/period_base.py`
2. Remove `from app.services.period_base import PeriodServiceBase` in `period.py`
3. Change `class PeriodService(PeriodServiceBase):` to `class PeriodService:`

**Pros:** 42 lines removed, one fewer file, no loss of functionality

**Cons:** If a mock PeriodService is needed in tests later, it can extend the concrete class or use `MagicMock`

**Effort:** 10 minutes

**Risk:** Low

---

### Option 2: Wire the ABC in DI

**Approach:** Update `dependencies.py` and routes to type-hint against `PeriodServiceBase`.

**Pros:** Makes the ABC pay its way

**Cons:** Still no alternate implementation; the ABC is still speculative

**Effort:** 20 minutes

**Risk:** Low

## Recommended Action

Option 1: delete `period_base.py`. There is one implementation and no injection point that needs the abstraction. If a test double is needed in the future, it can be created then.

## Technical Details

**Affected files:**
- `backend/app/services/period_base.py` — DELETE
- `backend/app/services/period.py:17` — remove import
- `backend/app/services/period.py:30` — remove `(PeriodServiceBase)` parent

## Acceptance Criteria

- [ ] `period_base.py` deleted
- [ ] `period.py` import and parent class reference removed
- [ ] All tests still pass

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Confirmed ABC not referenced in DI or routes
- Compared with LLMProvider ABC (legitimately used)
- Flagged as YAGNI violation
