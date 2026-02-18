# Symptom Logging API

**Feature:** Daily symptom log creation and retrieval
**Phase:** 2 (see [DESIGN.md §14](../DESIGN.md#14-development-phases))
**Files:**

| File | Purpose |
|---|---|
| `backend/app/models/symptoms.py` | Pydantic request/response models |
| `backend/app/api/routes/symptoms.py` | Route handlers + auth dependency |
| `backend/app/core/supabase.py` | Async Supabase client singleton |
| `backend/tests/api/routes/test_symptoms.py` | 23 pytest tests |

---

## Endpoints

### `POST /api/symptoms/logs`

Create a new symptom log entry for the authenticated user.

**Auth:** Bearer JWT required
**Status codes:** `201 Created` · `401 Unauthorized` · `422 Unprocessable Entity` · `500 Internal Server Error`

**Request body:**

```json
{
  "symptoms": ["fatigue", "brain_fog"],
  "source": "cards",
  "free_text_entry": null,
  "logged_at": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `symptoms` | `string[]` | Conditional | Required when `source` is `"cards"` or `"both"` |
| `source` | `"cards" \| "text" \| "both"` | Yes | How the log was created |
| `free_text_entry` | `string \| null` | Conditional | Required when `source` is `"text"` or `"both"` |
| `logged_at` | `datetime \| null` | No | ISO 8601 timestamp; defaults to `NOW()` in Supabase if omitted |

**Response body (`201`):**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "logged_at": "2024-03-15T10:00:00+00:00",
  "symptoms": ["fatigue", "brain_fog"],
  "free_text_entry": null,
  "source": "cards"
}
```

---

### `GET /api/symptoms/logs`

Retrieve symptom logs for the authenticated user, ordered newest-first.

**Auth:** Bearer JWT required
**Status codes:** `200 OK` · `401 Unauthorized` · `422 Unprocessable Entity` · `500 Internal Server Error`

**Query parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `start_date` | `date` | — | ISO 8601 date (`YYYY-MM-DD`). Inclusive, interpreted as `00:00:00 UTC` |
| `end_date` | `date` | — | ISO 8601 date (`YYYY-MM-DD`). Inclusive, interpreted as `23:59:59 UTC` |
| `limit` | `int` | `50` | Min `1`, max `100` |

**Response body (`200`):**

```json
{
  "logs": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "logged_at": "2024-03-15T10:00:00+00:00",
      "symptoms": ["fatigue", "brain_fog"],
      "free_text_entry": null,
      "source": "cards"
    }
  ],
  "count": 1,
  "limit": 50
}
```

Note: `count` reflects the number of logs returned in this response, not the total in the database. It will be ≤ `limit`.

---

## Data Model

Maps to the `symptom_logs` table (see [DESIGN.md §9](../DESIGN.md#9-data-models)):

```sql
symptom_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
  logged_at       TIMESTAMPTZ DEFAULT NOW(),
  symptoms        TEXT[],         -- array of symptom tag IDs
  free_text_entry TEXT,
  source          TEXT CHECK (source IN ('cards', 'text', 'both'))
)
```

The `symptoms` array contains IDs from the `symptoms_reference` table. No foreign key constraint is enforced at the DB level — the frontend is responsible for sending valid IDs.

---

## Authentication

All endpoints use the `get_current_user_id` FastAPI dependency:

```
Authorization: Bearer <supabase-jwt>
          │
          ▼
supabase.auth.get_user(token)   ← network call to Supabase Auth
          │
          ▼
    user.id (UUID string)  ← injected into route handler
```

The `user_id` in every DB operation is **always** derived from the validated JWT. Callers cannot specify a different `user_id` in the request body — the field is not exposed on the request model. Supabase RLS provides a second enforcement layer at the database level.

**401 cases:**
- Missing `Authorization` header → `"Missing authorization header"`
- Header present but not `Bearer <token>` format → `"Invalid authorization header format..."`
- Token invalid or expired (Supabase raises an exception) → `"Invalid or expired token"`

---

## Pydantic Models

### `SymptomLogCreate` (request)

Cross-field validation enforced by `@model_validator(mode="after")`:

| `source` | `symptoms` | `free_text_entry` |
|---|---|---|
| `"cards"` | must be non-empty | optional |
| `"text"` | ignored (may be empty) | must be non-empty |
| `"both"` | must be non-empty | must be non-empty |

Violations return `422` with Pydantic's standard error format.

### `SymptomLogResponse` (response)

Returned from both endpoints. Configured with `from_attributes = True` so it can be constructed directly from Supabase row dicts.

### `SymptomLogList` (GET response wrapper)

Wraps the list with `count` (length of this page) and `limit` (the requested limit) so clients can detect when they've hit the limit and may need to paginate.

---

## Supabase Client

`backend/app/core/supabase.py` exports `get_client()`, a lazy singleton:

```python
async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        # Service role key bypasses RLS; endpoints enforce user isolation
        # by always filtering queries on the authenticated user_id.
        _client = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client
```

The service role key is intentional — it lets the backend issue admin-level DB queries (needed for future features like the summary cache and pattern analysis). User isolation is enforced at the query level, not the key level.

**In tests**, `get_client` is overridden via `app.dependency_overrides` so no real connections are ever made.

---

## Testing

**Run:**

```bash
cd backend
uv run pytest tests/api/routes/test_symptoms.py -v
```

**Coverage: 23 tests across two classes**

`TestCreateSymptomLog` (11 tests):
- Happy path for all three `source` values (`cards`, `text`, `both`)
- Explicit `logged_at` timestamp accepted
- 401 for missing header, malformed header, invalid/expired token
- 422 for each invalid `source`/content combination and missing required fields

`TestGetSymptomLogs` (12 tests):
- Happy path with default params
- Empty result returns `[]` not an error
- `start_date`, `end_date`, and both filters accepted
- Custom `limit` reflected in response
- 401/422 for auth and param validation failures
- Ordering verified (newest-first asserted on multi-log response)

**Mock strategy:**

Tests use `app.dependency_overrides[get_client]` to inject a `MagicMock` client. `MockQueryBuilder` implements the full Supabase fluent query builder interface (every method returns `self`, `execute()` is `async`) so arbitrary chains work without maintaining separate mocks per query shape. Cleanup always runs in `finally` blocks to prevent override leakage between tests.

---

## Error Handling Reference

| Scenario | Status | Detail |
|---|---|---|
| No `Authorization` header | `401` | `"Missing authorization header"` |
| Header not `Bearer <token>` | `401` | `"Invalid authorization header format..."` |
| Token invalid / expired | `401` | `"Invalid or expired token"` |
| Payload validation failure | `422` | Pydantic error detail |
| `limit` out of range (0 or >100) | `422` | Pydantic error detail |
| `start_date` / `end_date` not a date | `422` | Pydantic error detail |
| DB insert returns no data | `500` | `"Failed to create symptom log"` |
| DB exception on insert | `500` | `"Failed to create symptom log"` |
| DB exception on query | `500` | `"Failed to retrieve symptom logs"` |

All `500` errors are logged at `ERROR` level with `exc_info=True` for full tracebacks. `401` token failures are logged at `WARNING`.
