# Symptom Logging API

**Feature:** Daily symptom log creation and retrieval
**Phase:** 2 (see [DESIGN.md §14](../DESIGN.md#14-development-phases))
**Files:**

| File | Purpose |
|---|---|
| `backend/app/models/symptoms.py` | Pydantic request/response models |
| `backend/app/api/routes/symptoms.py` | Route handlers, auth dependency, enrichment helpers |
| `backend/app/services/symptoms.py` | `validate_symptom_ids` business logic |
| `backend/app/core/supabase.py` | Async Supabase client singleton |
| `backend/tests/api/routes/test_symptoms.py` | 27 pytest tests |

---

## Endpoints

### `POST /api/symptoms/logs`

Create a new symptom log entry for the authenticated user.

**Auth:** Bearer JWT required
**Status codes:** `201 Created` · `400 Bad Request` · `401 Unauthorized` · `422 Unprocessable Entity` · `500 Internal Server Error`

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
| `symptoms` | `string[]` | Conditional | UUIDs from `symptoms_reference.id`. Required when `source` is `"cards"` or `"both"`. Validated against the table on every create. |
| `source` | `"cards" \| "text" \| "both"` | Yes | How the log was created |
| `free_text_entry` | `string \| null` | Conditional | Required when `source` is `"text"` or `"both"` |
| `logged_at` | `datetime \| null` | No | ISO 8601 timestamp; defaults to `NOW()` in Supabase if omitted |

**Response body (`201`):**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "logged_at": "2024-03-15T10:00:00+00:00",
  "symptoms": [
    {"id": "uuid", "name": "Fatigue", "category": "general"},
    {"id": "uuid", "name": "Brain fog", "category": "cognitive"}
  ],
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
      "symptoms": [
        {"id": "uuid", "name": "Hot flashes", "category": "vasomotor"},
        {"id": "uuid", "name": "Brain fog", "category": "cognitive"}
      ],
      "free_text_entry": "Felt terrible during meeting",
      "source": "both"
    }
  ],
  "count": 1,
  "limit": 50
}
```

Note: `count` reflects the number of logs returned in this response, not the total in the database. It will be ≤ `limit`.

**Breaking change from v1:** `symptoms` was previously a `string[]` of raw UUIDs. It is now an array of `SymptomDetail` objects (`id`, `name`, `category`). The POST request format (array of UUIDs) is unchanged.

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

The `symptoms` array contains UUIDs from `symptoms_reference.id`. No foreign key constraint is enforced at the DB level, but the backend validates all IDs against `symptoms_reference` before inserting (see [Symptom ID Validation](#symptom-id-validation) below).

---

## Symptom ID Validation

**File:** `backend/app/services/symptoms.py`

Before inserting a log, the route calls `validate_symptom_ids(payload.symptoms, client)`. The function:

1. Returns immediately if `symptoms` is empty (valid for `source="text"` logs).
2. Deduplicates the input with `set()` before querying — duplicate IDs in the request do not cause a false failure.
3. Queries `symptoms_reference` with `.in_("id", unique_ids)`.
4. Compares the row count returned against the number of unique IDs requested. Any mismatch means one or more IDs are absent.
5. Raises `400` with the list of missing IDs in the detail string.

```python
# Example 400 response body
{
  "detail": "Invalid symptom IDs: ['00000000-0000-0000-0000-000000000099']"
}
```

**Why a service, not inline in the route?** The validation is business logic independent of HTTP concerns. Extracting it to `services/symptoms.py` makes it straightforward to reuse (e.g. future bulk-log or import endpoints) and to unit-test in isolation without spinning up the full FastAPI app.

**Why not a DB foreign key?** `symptoms_reference.id` is a UUID primary key on a reference table. A foreign key on `symptom_logs.symptoms` (a `TEXT[]` array) is not straightforward in PostgreSQL. The application-level check is the practical solution for V1.

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

### `SymptomDetail`

Represents an enriched symptom entry resolved from `symptoms_reference`:

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | UUID from `symptoms_reference.id` |
| `name` | `str` | Human-readable symptom name, e.g. `"Hot flashes"` |
| `category` | `str` | Symptom category, e.g. `"vasomotor"`, `"cognitive"` |

If a symptom ID stored in a log is absent from `symptoms_reference` (data integrity anomaly), a fallback `SymptomDetail` is used: `name` equals the raw ID and `category` is `"unknown"`. A `WARNING` is logged.

### `SymptomLogCreate` (request)

Cross-field validation enforced by `@model_validator(mode="after")`:

| `source` | `symptoms` | `free_text_entry` |
|---|---|---|
| `"cards"` | must be non-empty | optional |
| `"text"` | ignored (may be empty) | must be non-empty |
| `"both"` | must be non-empty | must be non-empty |

Violations return `422` with Pydantic's standard error format.

The `symptoms` field accepts an array of UUID strings (unchanged from before — the enrichment is response-only).

### `SymptomLogResponse` (response)

Returned from both `POST` and `GET` endpoints. The `symptoms` field is now `list[SymptomDetail]` enriched via a join against `symptoms_reference`.

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

**Coverage: 27 tests across two classes**

`TestCreateSymptomLog` (13 tests):
- Happy path for all three `source` values (`cards`, `text`, `both`) — response `symptoms` verified as enriched objects
- Explicit `logged_at` timestamp accepted
- 401 for missing header, malformed header, invalid/expired token
- 422 for each invalid `source`/content combination and missing required fields
- 400 when all symptom IDs are absent from `symptoms_reference`
- 400 when a subset of symptom IDs are absent (partial failure); missing ID named in error

`TestGetSymptomLogs` (14 tests):
- Happy path with default params; `symptoms` verified as `SymptomDetail` objects
- Empty result returns `[]` not an error
- `start_date`, `end_date`, and both filters accepted
- Custom `limit` reflected in response
- 401/422 for auth and param validation failures
- Ordering verified (newest-first asserted on multi-log response)
- Enrichment verified end-to-end with explicit `name` and `category` field assertions
- Fallback for orphaned symptom IDs (absent from `symptoms_reference`): returns `category="unknown"` instead of failing

**Mock strategy:**

Tests use `app.dependency_overrides[get_client]` to inject a `MagicMock` client. `MockQueryBuilder` implements the full Supabase fluent query builder interface (every method — including `.in_()` — returns `self`, `execute()` is `async`) so arbitrary chains work without maintaining separate mocks per query shape.

`make_mock_client` uses `mock.table.side_effect` to dispatch different `MockQueryBuilder` instances by table name. This lets the `symptoms_reference` query and the `symptom_logs` query return independent data in the same test.

`make_ref_data(ids)` builds `{"id": ..., "name": "Symptom <id>", "category": "general"}` rows for a set of IDs, covering both the validation query (POST) and the enrichment lookup (GET/POST). Tests that verify enriched field values supply their own explicit `symptoms_ref_data`.

Cleanup always runs in `finally` blocks to prevent override leakage between tests.

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
| Any symptom ID not in `symptoms_reference` | `400` | `"Invalid symptom IDs: [...]"` |
| DB exception querying `symptoms_reference` | `500` | `"Failed to validate symptom IDs"` |
| DB insert returns no data | `500` | `"Failed to create symptom log"` |
| DB exception on insert | `500` | `"Failed to create symptom log"` |
| DB exception on log query | `500` | `"Failed to retrieve symptom logs"` |

All `500` errors are logged at `ERROR` level with `exc_info=True` for full tracebacks. `401` token failures are logged at `WARNING`.
