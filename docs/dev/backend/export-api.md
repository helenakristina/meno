# Export API

**Last Updated:** February 2026
**Base URL:** `/api/export`
**Auth:** All endpoints require `Authorization: Bearer <jwt>` header.

---

## Overview

The export endpoints allow authenticated users to download their symptom data in two formats:

| Format | Endpoint | Use Case |
|--------|----------|----------|
| PDF | `POST /api/export/pdf` | Clinical provider visit summary with AI-generated insights |
| CSV | `POST /api/export/csv` | Raw data for spreadsheet import or personal records |

Both endpoints share the same request body and validation rules.

---

## Request Body

```json
{
  "date_range_start": "2024-03-01",
  "date_range_end": "2024-03-31"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `date_range_start` | `date` (ISO 8601) | Start of the export window (inclusive) |
| `date_range_end` | `date` (ISO 8601) | End of the export window (inclusive) |

**Validation:**
- `date_range_start` must be ≤ `date_range_end`
- `date_range_end` cannot be in the future
- At least one symptom log must exist in the date range

---

## POST /api/export/pdf

Generates a clinical PDF provider summary.

### Response

**200 OK** — PDF binary file
`Content-Type: application/pdf`
`Content-Disposition: attachment; filename="meno-summary-YYYY-MM-DD-YYYY-MM-DD.pdf"`

### PDF Structure

| Section | Content |
|---------|---------|
| **Header** | "Meno Health Summary", date range, generation date |
| **Section 1** | AI-generated symptom pattern summary (2–3 paragraphs) |
| **Section 2** | Frequency table — top 10 most-logged symptoms with count and category |
| **Section 3** | Co-occurrence highlights — top 5 symptom pairs that appeared together |
| **Section 4** | Suggested provider questions — 5–7 AI-generated questions |
| **Footer** | Medical disclaimer |

### AI Content Guidelines

The LLM (gpt-4o-mini) is constrained to:
- Use "logs show" / "data indicates" language — never "you have" or "you are experiencing"
- Present observations, never diagnoses or causes
- Suggest questions using "Could you help me understand..." or "What might explain..."
- Never mention specific medications or treatments

### Errors

| Status | Condition |
|--------|-----------|
| 400 | `date_range_start` > `date_range_end` |
| 400 | `date_range_end` is in the future |
| 400 | No symptom logs found for the selected date range |
| 401 | Missing, malformed, or expired auth token |
| 500 | OpenAI API failure or PDF generation error |

### Example (curl)

```bash
curl -X POST https://api.meno.health/api/export/pdf \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"date_range_start":"2024-03-01","date_range_end":"2024-03-31"}' \
  --output meno-summary.pdf
```

---

## POST /api/export/csv

Downloads raw symptom logs as a CSV file.

### Response

**200 OK** — CSV text file
`Content-Type: text/csv`
`Content-Disposition: attachment; filename="meno-logs-YYYY-MM-DD-YYYY-MM-DD.csv"`

### CSV Format

```
date,symptoms,free_text_notes
2024-03-01,Hot flashes,Woke up three times
2024-03-03,Hot flashes,Fatigue,
2024-03-07,,Feeling foggy and low energy
```

| Column | Type | Description |
|--------|------|-------------|
| `date` | `YYYY-MM-DD` | UTC date of the log entry |
| `symptoms` | `string` | Comma-separated symptom names (empty if text-only log) |
| `free_text_notes` | `string` | User's free-text note (empty if none) |

**Notes:**
- Rows are ordered oldest-first
- Symptom IDs are resolved to human-readable names
- Compatible with Excel, Google Sheets, and Numbers
- No PII or account data is included

### Errors

| Status | Condition |
|--------|-----------|
| 400 | `date_range_start` > `date_range_end` |
| 400 | `date_range_end` is in the future |
| 400 | No symptom logs found for the selected date range |
| 401 | Missing, malformed, or expired auth token |
| 500 | Database query failure |

### Example (curl)

```bash
curl -X POST https://api.meno.health/api/export/csv \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"date_range_start":"2024-03-01","date_range_end":"2024-03-31"}' \
  --output meno-logs.csv
```

---

## Implementation Notes

### Data Flow

```
POST /api/export/pdf
  │
  ├── Validate date range
  ├── Fetch symptom_logs (logged_at, symptoms, free_text_entry)
  ├── Fetch symptoms_reference (resolve IDs → names)
  ├── Calculate frequency stats (Counter of symptom IDs)
  ├── Calculate co-occurrence stats (itertools.combinations)
  ├── Call OpenAI gpt-4o-mini for summary (~1–3s)
  ├── Call OpenAI gpt-4o-mini for questions (~1–3s)
  ├── Build PDF with reportlab (~<1s)
  ├── Record export in exports table (non-critical)
  └── Return PDF bytes

POST /api/export/csv
  │
  ├── Validate date range
  ├── Fetch symptom_logs (logged_at, symptoms, free_text_entry)
  ├── Fetch symptoms_reference (resolve IDs → names)
  ├── Build CSV with csv.writer
  ├── Record export in exports table (non-critical)
  └── Return CSV string
```

### Performance

- PDF adds 2–4 seconds for OpenAI generation (acceptable for a download)
- CSV is fast (<100ms) — no LLM calls
- Both use a single Supabase query for logs and one for symptom names

### Exports Table

Export records are written to the `exports` table (non-critical — failure is logged as a warning but does not fail the request):

```sql
INSERT INTO exports (user_id, export_type, date_range_start, date_range_end)
VALUES ($1, 'pdf'|'csv', $2, $3);
```

### LLM Service (`backend/app/services/llm.py`)

The `llm.py` service is designed for easy migration from OpenAI → Claude. See the LLM provider strategy in `CLAUDE.md` for migration instructions.

Functions:
- `generate_symptom_summary(freq_stats, coocc_stats, date_range) → str`
- `generate_provider_questions(freq_stats, coocc_stats, user_context) → list[str]`

---

## Files

| File | Purpose |
|------|---------|
| `backend/app/models/export.py` | `ExportRequest` Pydantic model |
| `backend/app/services/llm.py` | OpenAI wrapper for summary + questions |
| `backend/app/api/routes/export.py` | Route handlers + PDF/CSV builders |
| `backend/tests/api/routes/test_export.py` | Unit tests (mocked Supabase + LLM) |
