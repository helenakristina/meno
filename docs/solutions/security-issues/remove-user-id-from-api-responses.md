---
title: "Remove user_id from API response models — unnecessary PII exposure"
category: security-issues
date: 2026-03-17
tags: [security, pii, api-design, pydantic, backend]
---

# Remove `user_id` from API response models

## Problem

Response models that include `user_id: str` return the user's Supabase UUID to the browser on every API call. The frontend already knows the user's identity via the auth token — it doesn't need the UUID in response payloads. Every browser extension, analytics script, or XHR interceptor can now correlate sensitive data (e.g., period logs) to a specific account UUID.

**Affected model:** `PeriodLogResponse` included `user_id: str` returned on all of:
- `GET /api/period/logs`
- `POST /api/period/logs`
- `PATCH /api/period/logs/{id}`

## Root Cause

The response model was scaffolded from the database row shape, which includes `user_id` as a column. Response models should be designed for what the **client needs**, not as a reflection of the database row.

## Solution

Remove `user_id` from the Pydantic response model:

```python
# ❌ Before
class PeriodLogResponse(BaseModel):
    id: str
    user_id: str  # ← unnecessary PII
    period_start: date
    ...

# ✅ After
class PeriodLogResponse(BaseModel):
    id: str
    period_start: date
    ...
```

Pydantic's `from_attributes = True` config (used via `model_validate(row)`) will simply ignore the `user_id` field from the DB row — no additional mapping needed.

## Prevention

When scaffolding response models from DB schemas:
- Ask: "Does the client actually need this field?"
- User identifiers (`user_id`, `user_uuid`) are almost never needed in response payloads when the client authenticated the request.
- Audit response models as part of security review for any new endpoint.

## Files in this Codebase

- `backend/app/models/period.py` — `PeriodLogResponse`
- `backend/tests/api/routes/test_period.py` — `PERIOD_LOG` fixture (also remove `user_id`)
- `backend/tests/services/test_period_service.py` — `make_log()` helper (also remove `user_id`)
