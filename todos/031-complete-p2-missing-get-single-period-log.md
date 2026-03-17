---
status: pending
priority: p2
issue_id: "031"
tags: [code-review, api-design, backend, agent-native]
dependencies: []
---

# Missing `GET /api/period/logs/{id}` endpoint — agent cannot inspect a specific log

## Problem Statement

The API has no single-resource GET for a period log. An agent (or programmatic client) that stores a log ID from a POST response has no way to retrieve that specific log later without fetching the entire list and scanning it. The UI works around this with local state, but stateless API consumers cannot.

## Findings

- **File**: `backend/app/api/routes/period.py` — no single-resource GET
- 10/12 UI capabilities are agent-accessible; this is one of 2 critical gaps

## Proposed Solution

```python
@router.get("/logs/{log_id}", response_model=PeriodLogResponse)
async def get_period_log(
    log_id: str,
    user_id: CurrentUser,
    service: PeriodService = Depends(get_period_service),
) -> PeriodLogResponse:
    return await service.get_log(user_id, log_id)
```

Add `get_log(user_id, log_id)` to service + repository (uses double-eq IDOR pattern).

## Acceptance Criteria
- [ ] `GET /api/period/logs/{id}` returns `PeriodLogResponse` for own logs
- [ ] Returns 404 for other users' logs
- [ ] IDOR test added to `test_period_repository.py`
