---
status: pending
priority: p1
issue_id: "030"
tags: [code-review, performance, backend, async]
dependencies: []
---

# Sequential DB calls in `AskMenoService.ask()` — should use `asyncio.gather`

## Problem Statement

Two independent async DB calls in `ask()` are executed sequentially:
```python
analysis = await self.period_repo.get_cycle_analysis(user_id)
settings = await self.user_repo.get_settings(user_id)
```
These have no dependency on each other. Sequential execution adds 60–160ms of extra latency to every Ask Meno request (2× Supabase RTT).

## Findings

- **File**: `backend/app/services/ask_meno.py:138-139`
- Combined latency: T(get_cycle_analysis) + T(get_settings) ≈ 60–160ms
- Parallel latency: max(T_a, T_b) ≈ 30–80ms
- This runs on every LLM call, making it a hot path

## Proposed Solution

```python
import asyncio

results = await asyncio.gather(
    self.period_repo.get_cycle_analysis(user_id),
    self.user_repo.get_settings(user_id),
    return_exceptions=True,
)
analysis = results[0] if not isinstance(results[0], Exception) else None
settings_result = results[1] if not isinstance(results[1], Exception) else None

if settings_result is not None:
    has_uterus = settings_result.has_uterus
if analysis is not None and not isinstance(analysis, Exception):
    cycle_context = { ... }
```

## Acceptance Criteria
- [ ] Both calls use `asyncio.gather` with `return_exceptions=True`
- [ ] Graceful degradation preserved — exceptions treated as None
- [ ] Test verifies cycle context is enriched when both succeed
