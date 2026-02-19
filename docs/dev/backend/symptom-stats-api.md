# Symptom Statistics API

Two read-only endpoints that power the dashboard's analytics cards.

---

## `GET /api/symptoms/stats/frequency`

**Tags:** `symptoms`
**Auth required:** Yes (Bearer JWT)

### Overview

Returns per-symptom occurrence counts for the authenticated user within a date range. Powers the **Most Frequent Symptoms** bar chart on the dashboard (DESIGN.md §10.3).

Counts are total occurrences across all logs, not unique days. A symptom appearing in three separate logs on the same day contributes 3 to its count.

### Query Parameters

| Parameter    | Type   | Required | Default     | Description                              |
| ------------ | ------ | -------- | ----------- | ---------------------------------------- |
| `start_date` | `date` | No       | 30 days ago | Start of range, inclusive (ISO 8601 UTC) |
| `end_date`   | `date` | No       | Today       | End of range, inclusive (ISO 8601 UTC)   |

### Response `200 OK`

```json
{
  "stats": [
    {
      "symptom_id": "uuid",
      "symptom_name": "Hot flashes",
      "category": "vasomotor",
      "count": 15
    },
    {
      "symptom_id": "uuid",
      "symptom_name": "Brain fog",
      "category": "cognitive",
      "count": 12
    }
  ],
  "date_range_start": "2024-01-20",
  "date_range_end": "2024-02-19",
  "total_logs": 25
}
```

`stats` is sorted by `count` descending. Symptom IDs present in logs but absent from `symptoms_reference` are silently omitted (data-integrity anomaly, logged as a warning server-side).

### Error Responses

| Status | Condition                                   |
| ------ | ------------------------------------------- |
| `400`  | `start_date` is after `end_date`            |
| `401`  | Missing, malformed, or expired Bearer token |
| `422`  | Invalid date format in query parameters     |
| `500`  | Database query failed                       |

### Implementation Notes

- All date filters are converted to UTC timestamps covering the full day (`00:00:00` – `23:59:59`).
- Two Supabase queries:
  1. `symptom_logs` — fetch `symptoms` arrays for the user in the date range.
  2. `symptoms_reference` — resolve symptom IDs to names and categories.
- Counting uses `collections.Counter` on the flattened symptom ID list.

---

## `GET /api/symptoms/stats/cooccurrence`

**Tags:** `symptoms`
**Auth required:** Yes (Bearer JWT)

### Overview

Returns pairs of symptoms that appear together frequently in the user's logs, within a date range. Powers the **"Symptoms that travel together"** card on the dashboard (DESIGN.md §10.3, V2).

Co-occurrence is calculated from `symptom1`'s perspective: `cooccurrence_rate = logs_containing_both / logs_containing_symptom1`. This is intentionally asymmetric — the pair `(A→B)` may have a different rate than `(B→A)`.

### Query Parameters

| Parameter       | Type   | Required | Default     | Description                                                    |
| --------------- | ------ | -------- | ----------- | -------------------------------------------------------------- |
| `start_date`    | `date` | No       | 30 days ago | Start of range, inclusive (ISO 8601 UTC)                       |
| `end_date`      | `date` | No       | Today       | End of range, inclusive (ISO 8601 UTC)                         |
| `min_threshold` | `int`  | No       | `2`         | Exclude pairs that appear together fewer than this many times  |

`min_threshold` must be ≥ 1 (422 if zero or negative).

### Response `200 OK`

```json
{
  "pairs": [
    {
      "symptom1_id": "uuid-a",
      "symptom1_name": "Hot flashes",
      "symptom2_id": "uuid-b",
      "symptom2_name": "Brain fog",
      "cooccurrence_count": 12,
      "cooccurrence_rate": 0.8,
      "total_occurrences_symptom1": 15
    }
  ],
  "date_range_start": "2024-01-20",
  "date_range_end": "2024-02-19",
  "total_logs": 25,
  "min_threshold": 2
}
```

`pairs` is sorted by `cooccurrence_rate` descending, capped at 10 pairs.

### Error Responses

| Status | Condition                                   |
| ------ | ------------------------------------------- |
| `400`  | `start_date` is after `end_date`            |
| `401`  | Missing, malformed, or expired Bearer token |
| `422`  | `min_threshold` < 1, or invalid date format |
| `500`  | Database query failed                       |

### Implementation Notes

- Symptom pairs are generated with `itertools.combinations(sorted(unique_symptoms_per_log), 2)`. Sorting ensures canonical pair order (same pair is never counted twice).
- Symptoms are deduplicated within each log before pair generation, so a log with `[A, A, B]` counts as one occurrence of `(A, B)`.
- Individual symptom occurrence counts (`symptom_counts`) and pair counts (`pair_counts`) are accumulated in a single pass using `Counter` and `defaultdict`.
- Pairs where either symptom ID is absent from `symptoms_reference` are silently omitted.
- Response is capped at `_MAX_PAIRS = 10`.

---

## Source Files

| Role   | Path                                        |
| ------ | ------------------------------------------- |
| Models | `backend/app/models/symptoms.py`            |
| Route  | `backend/app/api/routes/symptoms.py`        |
| Tests  | `backend/tests/api/routes/test_symptoms.py` |
