# Symptom Statistics API

**Endpoint:** `GET /api/symptoms/stats/frequency`
**Tags:** `symptoms`
**Auth required:** Yes (Bearer JWT)

---

## Overview

Returns per-symptom occurrence counts for the authenticated user within a
date range. Designed to power the **Symptom Frequency Chart** on the dashboard
(DESIGN.md §10.3).

Counts are total occurrences across all logs, not unique days. A symptom
appearing in three separate logs on the same day contributes 3 to its count.

---

## Query Parameters

| Parameter    | Type   | Required | Default       | Description                              |
| ------------ | ------ | -------- | ------------- | ---------------------------------------- |
| `start_date` | `date` | No       | 30 days ago   | Start of range, inclusive (ISO 8601 UTC) |
| `end_date`   | `date` | No       | Today         | End of range, inclusive (ISO 8601 UTC)   |

---

## Response `200 OK`

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

`stats` is sorted by `count` descending. Symptom IDs present in logs but
absent from `symptoms_reference` are silently omitted (data-integrity anomaly,
logged as a warning server-side).

---

## Error Responses

| Status | Condition                                   |
| ------ | ------------------------------------------- |
| `400`  | `start_date` is after `end_date`            |
| `401`  | Missing, malformed, or expired Bearer token |
| `422`  | Invalid date format in query parameters     |
| `500`  | Database query failed                       |

---

## Implementation Notes

- All date filters are converted to UTC timestamps covering the full day
  (`00:00:00` – `23:59:59`).
- The endpoint makes two Supabase queries:
  1. `symptom_logs` — fetch `symptoms` arrays for the user in the date range.
  2. `symptoms_reference` — resolve symptom IDs to names and categories.
- Counting uses `collections.Counter` on the flattened symptom ID list.
- No pagination; returns all matching symptom counts. For a user with 1 000
  logs each containing ~5 symptoms, this is a lightweight in-process `Counter`
  operation and does not require optimization in V1.

---

## Source files

| Role   | Path                                              |
| ------ | ------------------------------------------------- |
| Models | `backend/app/models/symptoms.py`                  |
| Route  | `backend/app/api/routes/symptoms.py`              |
| Tests  | `backend/tests/api/routes/test_symptoms.py`       |
