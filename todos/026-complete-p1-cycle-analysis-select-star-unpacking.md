---
status: pending
priority: p1
issue_id: "026"
tags: [code-review, pydantic, backend, database]
dependencies: []
---

# `get_cycle_analysis` uses `select("*")` + `**row` unpacking — breaks on new columns

## Problem Statement

`PeriodRepository.get_cycle_analysis` does `CycleAnalysisResponse(**response.data[0])`. `CycleAnalysisResponse` has no `extra='ignore'` config. If the `cycle_analysis` table gains any new column (e.g. `updated_at`, `has_sufficient_data`), Pydantic will raise a `ValidationError` on every analysis fetch. This is a silent time-bomb.

## Findings

- **File**: `backend/app/repositories/period_repository.py:299`
- `CycleAnalysisResponse` uses `model_config = {"from_attributes": True}` but no `extra="ignore"`
- Same issue would apply if a DB migration adds any column not in the model

## Proposed Solutions

**Option A (Preferred):** Select only needed columns:
```python
response = await self.client.table("cycle_analysis")
    .select("average_cycle_length, cycle_variability, months_since_last_period, inferred_stage, calculated_at")
    .eq("user_id", user_id).limit(1).execute()
```

**Option B:** Add `extra="ignore"` to model config:
```python
model_config = {"from_attributes": True, "extra": "ignore"}
```

## Acceptance Criteria
- [ ] `get_cycle_analysis` is resilient to extra DB columns
- [ ] Either explicit column selection or `extra="ignore"` on model
