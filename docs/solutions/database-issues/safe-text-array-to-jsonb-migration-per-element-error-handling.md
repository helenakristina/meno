---
title: Safe TEXT[] to JSONB Migration with Per-Element Error Handling
category: database-issues
date: 2026-04-04
tags:
  [postgresql, migration, jsonb, text-array, data-integrity, supabase, plpgsql]
modules: [appointment_prep, migrations]
symptoms:
  - Existing rows silently dropped from UPDATE when array is empty
  - Single malformed JSON element aborts entire migration UPDATE
  - Re-running migration drops already-migrated JSONB column
related_files:
  - backend/app/migrations/migrate_concerns_text_array_to_jsonb.sql
  - backend/app/models/appointment.py
---

## Problem Description

When migrating a column from `TEXT[]` to `JSONB` (e.g., converting plain string concerns to structured `{text, comment}` objects), a naive approach using a single `UPDATE ... WHERE array_length(concerns, 1) > 0` has three silent failure modes that corrupt or lose data.

## Root Cause

Three distinct PostgreSQL behaviors interact badly in naive migrations:

**Bug 1 — Empty array silently dropped:**
`array_length('{}', 1)` returns `NULL` (not `0`) in PostgreSQL. A `WHERE array_length(concerns, 1) > 0` guard evaluates `NULL > 0` → `false`, so rows with `concerns = '{}'` are never updated. They stay as `TEXT[]` while the column is dropped, losing the empty array entirely.

**Bug 2 — One malformed element aborts all rows:**
A single invalid JSON string (e.g., `'{"text": "unclosed'`) inside any row's array causes `::jsonb` cast to throw `invalid_text_representation`, rolling back the entire `UPDATE` block. All other rows fail even if their data is perfectly valid.

**Bug 3 — Not idempotent (re-run drops migrated data):**
The `DROP COLUMN concerns / RENAME concerns_jsonb TO concerns` step runs unconditionally. If the migration is re-run after the rename has already happened, it drops the already-migrated JSONB `concerns` column, destroying all data.

## Working Solution

Use a PL/pgSQL `DO` block with per-row, per-element `EXCEPTION` handling, plus an idempotency guard on the DROP/RENAME step.

```sql
-- Step 1: Add staging column
ALTER TABLE appointment_prep_contexts
  ADD COLUMN IF NOT EXISTS concerns_jsonb JSONB DEFAULT NULL;

-- Step 2: Back-fill with per-element exception handling
DO $$
DECLARE
  rec RECORD;
  elem TEXT;
  result JSONB;
  elem_jsonb JSONB;
BEGIN
  FOR rec IN
    SELECT id, concerns
    FROM appointment_prep_contexts
    WHERE concerns IS NOT NULL
  LOOP
    -- Fix Bug 1: array_length returns NULL for '{}', not 0
    IF array_length(rec.concerns, 1) IS NULL THEN
      UPDATE appointment_prep_contexts
        SET concerns_jsonb = '[]'::jsonb
        WHERE id = rec.id;
      CONTINUE;
    END IF;

    result := '[]'::jsonb;
    FOREACH elem IN ARRAY rec.concerns LOOP
      BEGIN
        IF elem ~ '^\s*\{' THEN
          -- Looks like JSON — try to parse it
          elem_jsonb := elem::jsonb;
          IF elem_jsonb ? 'text' THEN
            -- Already a {text: ...} object — use directly
            result := result || jsonb_build_array(elem_jsonb);
          ELSE
            -- JSON but no 'text' key — wrap as plain string
            result := result || jsonb_build_array(
              jsonb_build_object('text', elem, 'comment', NULL)
            );
          END IF;
        ELSE
          -- Plain string — wrap it
          result := result || jsonb_build_array(
            jsonb_build_object('text', elem, 'comment', NULL)
          );
        END IF;
      EXCEPTION
        -- Fix Bug 2: malformed JSON falls back to plain-string wrapping
        WHEN invalid_text_representation THEN
          result := result || jsonb_build_array(
            jsonb_build_object('text', elem, 'comment', NULL)
          );
      END;
    END LOOP;

    UPDATE appointment_prep_contexts
      SET concerns_jsonb = result
      WHERE id = rec.id;
  END LOOP;
END $$;

-- Step 3: Drop old column and rename — Fix Bug 3: idempotency guard
DO $$
BEGIN
  -- Only drop/rename if the staging column still exists
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'appointment_prep_contexts'
      AND column_name = 'concerns_jsonb'
  ) THEN
    ALTER TABLE appointment_prep_contexts DROP COLUMN concerns;
    ALTER TABLE appointment_prep_contexts RENAME COLUMN concerns_jsonb TO concerns;
  END IF;
END $$;

COMMENT ON COLUMN appointment_prep_contexts.concerns IS
  'Prioritized concerns from Step 3 as JSONB array: [{text: string, comment: string|null}]';
```

## Prevention

**Always use this 3-step pattern for TEXT[] → JSONB migrations:**

1. `ADD COLUMN IF NOT EXISTS` staging column
2. PL/pgSQL DO block with `FOREACH` + inner `BEGIN/EXCEPTION` per element
3. Drop/rename guarded by `IF EXISTS` check on staging column

**Checklist before running any TEXT[] → JSONB migration:**

- [ ] Take a backup: `CREATE TABLE foo_backup AS SELECT id, col FROM foo;`
- [ ] Verify empty-array rows are handled (`array_length IS NULL` check, not `> 0`)
- [ ] Wrap per-element cast in `EXCEPTION WHEN invalid_text_representation`
- [ ] Guard DROP/RENAME with `IF EXISTS` on staging column
- [ ] Test re-run safety: run migration twice on a copy — second run should be a no-op

**Pydantic side:** when the column type changes, update the response model immediately. In this case `ScenarioCard.sources: list[str]` also needed updating to `list[ScenarioSource]` because the LLM was already returning structured objects that didn't match the old type — a silent ValidationError in production.
