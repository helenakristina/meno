---
title: Frontend TypeScript Interface Doesn't Match Backend Pydantic Response
category: logic-errors
date: 2026-03-20
tags: [typescript, type-safety, api-integration, pydantic, medication-tracking]
symptoms:
  - "TypeError: Cannot read properties of undefined (reading 'length')"
  - Page crashes on load; loading skeleton renders then errors
  - No TypeScript compile error (masked by `as any` casts)
  - Backend returns 200 OK but frontend accesses nonexistent fields
components:
  - frontend/src/lib/types/api.ts (SymptomComparisonResponse, ComparisonRow)
  - frontend/src/routes/(app)/medications/[id]/impact/+page.svelte
---

## Problem

The medication Impact page crashed on load with `TypeError: Cannot read properties of undefined (reading 'length')`. The backend returned a valid 200 response, but the frontend TypeScript interfaces were written against a speculative shape that never matched the actual Pydantic model output.

## Root Cause

The `SymptomComparisonResponse` and `ComparisonRow` interfaces in `api.ts` were written before (or without reference to) the actual backend Pydantic models. The divergence was total — every field name or structure was wrong:

| Frontend expected | Backend actually returned | Crash impact |
|---|---|---|
| `comparison_rows: ComparisonRow[]` | `rows: ComparisonRow[]` | `data.comparison_rows.length` → undefined `.length` |
| `before_window: { start, end }` | `before_start`, `before_end` (flat) | Nested access fails |
| `after_window: { start, end }` | `after_start`, `after_end` (flat) | Nested access fails |
| `sparse_data: boolean` | `before_is_sparse`, `after_is_sparse` | Wrong field name |
| `before_frequency: number` | `before_pct: number` | Wrong field name |
| `after_frequency: number` | `after_pct: number` | Wrong field name |
| `direction: 'unchanged'` | `direction: 'stable'` | String comparison always false |
| (missing) | `has_after_data: boolean` | No UI state for "too recent" medications |

The bug was invisible until the page was visited because `as any` casts in the API client bypassed all TypeScript checking.

## Fix

Rewrote both interfaces to exactly match the backend Pydantic model field names and types.

**Before (wrong):**
```typescript
export interface ComparisonRow {
  symptom_name: string;
  category: string;
  before_frequency: number;  // ← doesn't exist
  after_frequency: number;   // ← doesn't exist
  change_pct: number;        // ← doesn't exist
  direction: 'improved' | 'worsened' | 'unchanged';  // ← 'unchanged' doesn't exist
}

export interface SymptomComparisonResponse {
  medication_name: string;
  medication_id: string;
  start_date: string;
  before_window: { start: string; end: string };  // ← doesn't exist (nested)
  after_window: { start: string; end: string };   // ← doesn't exist (nested)
  comparison_rows: ComparisonRow[];               // ← doesn't exist
  sparse_data: boolean;                           // ← doesn't exist
  has_confounding_changes: boolean;
}
```

**After (correct — matches backend `SymptomComparisonResponse` Pydantic model):**
```typescript
export interface ComparisonRow {
  symptom_id: string;
  symptom_name: string;
  category: string;
  before_count: number;
  before_days: number;
  before_pct: number;   // 0–100
  after_count: number;
  after_days: number;
  after_pct: number;    // 0–100
  direction: 'improved' | 'worsened' | 'stable';  // 'stable', not 'unchanged'
}

export interface SymptomComparisonResponse {
  medication_id: string;
  medication_name: string;
  dose: string;
  delivery_method: string;
  start_date: string;
  end_date: string | null;
  before_start: string | null;   // flat, not nested
  before_end: string | null;
  after_start: string | null;
  after_end: string | null;
  window_days: number;
  has_after_data: boolean;       // new — "too early to compare"
  before_log_days: number;
  after_log_days: number;
  before_is_sparse: boolean;
  after_is_sparse: boolean;
  rows: ComparisonRow[];         // not comparison_rows
  has_confounding_changes: boolean;
}
```

The impact page template was also updated to use the correct field names and to render a `has_after_data` warning for medications started too recently to have comparison data.

## How This Happens

Types written speculatively (before the backend exists, or without reading the actual Pydantic model) will drift. This project has `as any` casts on most dynamic-path API calls, which silences TypeScript and lets the mismatch compile and deploy undetected.

## Prevention

**When adding a new API endpoint, follow this order:**

1. **Backend first** — implement route + Pydantic response model + backend tests
2. **Read the actual model** — open `backend/app/models/` and copy the fields verbatim
3. **Write the TypeScript interface** — field names must be identical; `date` → `string`, `int/float` → `number`, `None` → `null`
4. **Add a comment** linking the interface to its Pydantic source:
   ```typescript
   // Mirrors backend app.models.medications.SymptomComparisonResponse
   export interface SymptomComparisonResponse { ... }
   ```

**Quick verification — check a live response shape:**
```bash
# Export OpenAPI schema from running backend
curl http://localhost:8000/openapi.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['components']['schemas']['SymptomComparisonResponse'], indent=2))"
```

**PR review checklist item:**
> For any new or changed API endpoint, confirm the TypeScript interface in `api.ts` was derived from the actual Pydantic `response_model=`, not written from memory.

## Related

- See also: `docs/solutions/logic-errors/backend-phase4-type-safety-and-interface-cleanup.md` — covers repository return type discipline on the backend side
- `docs/dev/frontend/V2CODE_EXAMPLES.md` Part 11 — type-safe API client with method overloads
