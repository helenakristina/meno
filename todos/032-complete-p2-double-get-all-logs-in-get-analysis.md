---
status: pending
priority: p2
issue_id: "032"
tags: [code-review, performance, backend]
dependencies: []
---

# `get_analysis` calls `get_all_logs` twice on cold start — redundant DB round-trip

## Problem Statement

When no cached analysis exists, `get_analysis` calls `_refresh_cycle_analysis` (which fetches all logs), then immediately calls `get_all_logs` AGAIN on line 133 to recompute `has_sufficient_data`. This flag is already correctly set inside `_refresh_cycle_analysis`. The second call is completely redundant.

## Findings

- **File**: `backend/app/services/period.py:128-137`
- `_refresh_cycle_analysis` sets `has_sufficient_data` at line 190
- `get_analysis` discards that value and recomputes it from a second DB fetch

## Proposed Solution

```python
async def get_analysis(self, user_id: str) -> CycleAnalysisResponse:
    analysis = await self.period_repo.get_cycle_analysis(user_id)
    if analysis is None:
        analysis = await self._refresh_cycle_analysis(user_id)
        return analysis  # has_sufficient_data already set correctly

    # For cached analysis, recompute has_sufficient_data
    all_logs = await self.period_repo.get_all_logs(user_id)
    cycle_lengths = [log.cycle_length for log in all_logs if log.cycle_length is not None]
    analysis.has_sufficient_data = len(cycle_lengths) >= MIN_CYCLES_FOR_ANALYSIS
    return analysis
```

Or better: persist `has_sufficient_data` to the `cycle_analysis` table to eliminate the second fetch in all paths.

## Acceptance Criteria
- [ ] Cold-start `get_analysis` makes at most 2 DB calls (not 3)
- [ ] `has_sufficient_data` is correctly set in all code paths
