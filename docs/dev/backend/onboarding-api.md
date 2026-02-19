# Onboarding API

**Endpoint:** `POST /api/users/onboarding`
**Auth:** Required (Bearer JWT)
**Status:** 201 Created on success

---

## Overview

Creates the user's profile row in `public.users` after Supabase Auth signup. Called exactly once per user, at the end of the onboarding flow.

The email is sourced from `auth.users` via the service role key — it is never accepted from the request body, ensuring the profile always reflects the verified auth identity.

---

## Request

**Headers**

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <supabase-jwt>` |
| `Content-Type` | Yes | `application/json` |

**Body**

```json
{
  "date_of_birth": "1975-06-15",
  "journey_stage": "perimenopause"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `date_of_birth` | `date` (ISO 8601) | Yes | Must be in the past; user must be ≥ 18 years old |
| `journey_stage` | `string` | Yes | One of: `perimenopause`, `menopause`, `post-menopause`, `unsure` |

---

## Response

**201 Created**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "date_of_birth": "1975-06-15",
  "journey_stage": "perimenopause",
  "onboarding_completed": true,
  "created_at": "2024-03-15T10:00:00+00:00"
}
```

---

## Error Responses

| Status | When |
|---|---|
| `400 Bad Request` | `date_of_birth` is today or in the future |
| `400 Bad Request` | User is under 18 years old |
| `401 Unauthorized` | Missing, malformed, or expired JWT |
| `409 Conflict` | Profile already exists for this user |
| `422 Unprocessable Entity` | Required field missing or `journey_stage` is not a valid value |
| `500 Internal Server Error` | Database insert or auth lookup failed |

---

## Implementation Notes

- **Duplicate prevention:** A select on `public.users` is performed before insert. If a row exists for the authenticated `user_id`, the endpoint returns 409.
- **Email sourcing:** `client.auth.admin.get_user_by_id(user_id)` fetches the email using the service role key. The request body never contains the email.
- **Age validation:** Calculated accurately — accounts for whether the user's birthday has occurred yet in the current year.
- **`onboarding_completed`** is always set to `true` by this endpoint; it is never accepted from the request.

---

## Files

| Path | Description |
|---|---|
| `backend/app/models/users.py` | `OnboardingRequest` and `UserResponse` Pydantic models |
| `backend/app/api/routes/users.py` | Route handler and auth dependency |
| `backend/tests/api/routes/test_users.py` | Unit tests (all Supabase calls mocked) |
