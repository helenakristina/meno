---
status: complete
priority: p2
issue_id: "054"
tags: [code-review, performance, backend, medications, asyncio, pr-2]
dependencies: []
---

# `get_context` issues two sequential DB queries that could be parallelized

## Problem Statement

`MedicationRepository.get_context` awaits two independent queries sequentially — one for active medications, one for recently stopped. Both hit the same table with no dependency on each other. On every Ask Meno request with MHT enabled, this adds one avoidable DB round-trip to the hot path.

## Findings

- `backend/app/repositories/medication_repository.py` lines 418–443
- `current_resp` is awaited, then `recent_resp` is awaited sequentially
- These are independent queries — neither depends on the result of the other
- The existing codebase uses `asyncio.gather` for exactly this pattern (e.g., `AskMenoService.ask` lines 156–158)
- Called on every Ask Meno request via `get_context_if_enabled` in `medication.py`
- Identified by performance-oracle and architecture-strategist

## Proposed Solutions

### Option 1: Use `asyncio.gather` for both queries (Recommended)

```python
current_resp, recent_resp = await asyncio.gather(
    self._supabase.table("user_medications")
        .select(...)
        .eq("user_id", user_id)
        .is_("end_date", "null")
        .order("start_date", desc=True)
        .execute(),
    self._supabase.table("user_medications")
        .select(...)
        .eq("user_id", user_id)
        .not_.is_("end_date", "null")
        .gte("end_date", cutoff.isoformat())
        .order("end_date", desc=True)
        .limit(5)
        .execute()
)
```

**Pros:** Halves I/O latency for this method, consistent with existing codebase pattern
**Effort:** Small
**Risk:** Low

## Recommended Action

Option 1 — straightforward gather, same pattern used elsewhere.

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py` lines 418–443

## Acceptance Criteria

- [ ] `get_context` uses `asyncio.gather` for both queries
- [ ] All existing tests pass
- [ ] Method still correctly returns `MedicationContext` with both active and recent medications

## Work Log

- 2026-03-18: Identified by performance-oracle and architecture-strategist in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
