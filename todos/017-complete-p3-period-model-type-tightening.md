---
status: pending
priority: p3
issue_id: "017"
tags: [code-review, backend, type-safety]
dependencies: []
---

# Tighten types in `period.py` models — `Optional[str]` → Literal types, `X | None`

## Problem Statement

Several type annotations in `backend/app/models/period.py` are weaker than they should be:

1. `PeriodLogResponse.flow_level: Optional[str]` — should be `FlowLevel | None` (the Literal type is defined at the top of the file but not used here)
2. `CycleAnalysisResponse.inferred_stage: Optional[str]` — should be `Literal["perimenopause", "menopause", "post-menopause"] | None` to match the DB CHECK constraint
3. `Optional[X]` style used throughout — project convention is `X | None` (Python 3.10+ syntax, used consistently in `users.py`)

## Findings

- `backend/app/models/period.py:38` — `flow_level: Optional[str] = None`
- `backend/app/models/period.py:64` — `inferred_stage: Optional[str] = None`
- Multiple `Optional[X]` usages across `period.py` vs `X | None` in `users.py`
- Python reviewer flagged all three

## Proposed Solutions

### Option 1: Update all three issues in one pass

1. Change `PeriodLogResponse.flow_level` to `FlowLevel | None = None`
2. Change `CycleAnalysisResponse.inferred_stage` to `Literal["perimenopause", "menopause", "post-menopause"] | None = None`
3. Replace all `Optional[X]` with `X | None` and remove `Optional` import if no longer needed

**Effort:** 15 minutes

**Risk:** Low — Pydantic accepts both `Optional[X]` and `X | None` identically; this is a style/correctness change

## Recommended Action

Option 1. Quick cleanup pass on period.py models.

## Technical Details

**Affected files:**
- `backend/app/models/period.py` — multiple type annotations

## Acceptance Criteria

- [ ] `PeriodLogResponse.flow_level` typed as `FlowLevel | None`
- [ ] `CycleAnalysisResponse.inferred_stage` typed as `Literal[...] | None`
- [ ] No `Optional[X]` usage in `period.py`
- [ ] All tests still pass

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
