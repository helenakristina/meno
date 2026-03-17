---
title: "asyncio.gather with return_exceptions=True for parallel optional enrichment"
category: performance-issues
date: 2026-03-17
tags: [fastapi, asyncio, python, performance, graceful-degradation]
modules: [ask_meno, period, services]
---

# asyncio.gather with return_exceptions=True for Optional Enrichment

## Problem Symptom

Sequential `await` calls for independent, supplementary data add latency on every request. In `AskMenoService.ask()`, fetching cycle analysis and user settings for LLM context enrichment were done one after the other — adding ~60-160ms per LLM call for data that is purely supplementary (the LLM still works without it).

```python
# Before: sequential — second call waits for first
analysis = await self.period_repo.get_cycle_analysis(user_id)
settings = await self.user_repo.get_settings(user_id)
```

## Root Cause

Two independent async DB calls that don't depend on each other were being awaited sequentially. Because both queries hit Supabase over the network, the total wait time was additive.

## Solution

Use `asyncio.gather(..., return_exceptions=True)` to run both calls concurrently. Check each result with `isinstance(result, Exception)` before using it — this is the graceful degradation pattern for supplementary data.

```python
import asyncio

# In AskMenoService.ask():
cycle_context: Optional[dict] = None
has_uterus: Optional[bool] = None

if self.period_repo is not None:
    try:
        analysis_result, settings_result = await asyncio.gather(
            self.period_repo.get_cycle_analysis(user_id),
            self.user_repo.get_settings(user_id),
            return_exceptions=True,
        )
        if not isinstance(settings_result, Exception):
            has_uterus = settings_result.has_uterus
        if not isinstance(analysis_result, Exception) and analysis_result is not None:
            cycle_context = {
                "average_cycle_length": analysis_result.average_cycle_length,
                "months_since_last_period": analysis_result.months_since_last_period,
                "inferred_stage": analysis_result.inferred_stage,
            }
    except Exception:
        pass  # Supplementary data — degrade gracefully
```

**Key details:**
- `return_exceptions=True` means exceptions from either coroutine are returned as values instead of raised — the outer `try/except` is a last-resort safety net only
- `isinstance(result, Exception)` is the idiomatic check; avoids the result being silently treated as data
- The outer `except Exception: pass` handles the rare case where `gather` itself fails (not individual coroutines)

## When to Apply This Pattern

Use `asyncio.gather(..., return_exceptions=True)` when:
1. Two or more DB/API calls are **independent** (neither result depends on the other)
2. The data is **supplementary** — the feature still works if one or both fail
3. You want **graceful degradation** without a try/except per call

Do NOT use `return_exceptions=True` when:
- A failure in either call should abort the whole operation (use plain `asyncio.gather` instead and let it raise)
- The calls are sequential by nature (B depends on A's result)

## Prevention

When adding multiple `await` calls in a service method, ask: "Are these independent?" If yes, gather them. For required data, use plain `asyncio.gather`. For optional enrichment, use `return_exceptions=True`.

## Related

- `backend/app/services/ask_meno.py` — where this pattern is applied
- [asyncio.gather docs](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
