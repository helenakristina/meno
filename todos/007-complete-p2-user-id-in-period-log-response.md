---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, backend, security, pii]
dependencies: []
---

# Remove `user_id` from `PeriodLogResponse` — unnecessary PII in API response

## Problem Statement

`PeriodLogResponse` includes `user_id: str` as a serialized field returned to the browser. The frontend already holds the user's identity via the Supabase auth token — it doesn't need the UUID in every log response. Exposing it unnecessarily means any browser extension, analytics script, or XHR interceptor can correlate period data to a specific Supabase account UUID.

## Findings

- `backend/app/models/period.py:36-46` — `PeriodLogResponse` has `user_id: str`
- Returned by: `GET /api/period/logs`, `POST /api/period/logs`, `PATCH /api/period/logs/{id}`, and inside `CreatePeriodLogResponse`
- Frontend (`period/+page.svelte`) never reads `user_id` from log objects
- Security sentinel flagged as Low-Medium severity

## Proposed Solutions

### Option 1: Exclude `user_id` from `PeriodLogResponse` using Pydantic `model_config`

**Approach:** The internal `_to_model()` method populates `user_id` for intra-service use. Create a separate `PeriodLogPublicResponse` without the field, or use `model_serializer` / `model_config` to exclude it from JSON output.

Simplest: just remove `user_id` from `PeriodLogResponse` entirely. The repository can keep the field in an internal dataclass if needed.

**Pros:** Eliminates unnecessary PII exposure, clean response schema

**Cons:** If any future internal use requires `user_id` on the response model, it would need to be re-added to an internal variant

**Effort:** 30 minutes

**Risk:** Low — frontend never reads this field

## Recommended Action

Remove `user_id` from `PeriodLogResponse`. It serves no client-side purpose and should not be in the public API response.

## Technical Details

**Affected files:**
- `backend/app/models/period.py:36-46` — `PeriodLogResponse`
- `frontend/src/lib/types/api.ts` — update `/api/period/logs` response type if `user_id` is currently listed

## Acceptance Criteria

- [ ] `PeriodLogResponse` does not include `user_id`
- [ ] `GET /api/period/logs` response objects do not contain `user_id`
- [ ] `POST /api/period/logs` response does not contain `user_id`
- [ ] Frontend type definitions updated accordingly

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Confirmed frontend never reads user_id from log objects
- Assessed exposure risk in browser environment
