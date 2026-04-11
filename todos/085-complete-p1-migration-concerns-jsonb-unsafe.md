---
status: pending
priority: p1
issue_id: "085"
tags: [code-review, database, migration, data-safety]
dependencies: []
---

# `migrate_concerns_text_array_to_jsonb.sql` has 3 data-safety bugs

## Problem Statement

The migration that converts `concerns TEXT[]` → JSONB has three bugs that can cause data loss or silent corruption. If the UPDATE aborts due to malformed JSON in any row, the DROP/RENAME still run and all concerns data is permanently destroyed.

## Findings

**File**: `backend/app/migrations/migrate_concerns_text_array_to_jsonb.sql`

### Bug 1 — Empty arrays silently become NULL (line 31)

```sql
WHERE concerns IS NOT NULL AND array_length(concerns, 1) > 0;
```

`array_length(concerns, 1)` returns `NULL` (not `0`) for `{}`. The condition evaluates to `NULL`, excluding empty-array rows from the UPDATE. After column rename, those rows get `concerns = NULL` instead of `concerns = '[]'::jsonb`. Fix: remove the `array_length` guard, or add explicit handling for empty arrays.

### Bug 2 — Malformed JSON aborts the entire UPDATE (line 24)

```sql
WHEN elem ~ '^\s*\{' AND (elem::jsonb) ? 'text'
```

If any element looks like JSON (starts with `{`) but is malformed (e.g. `{"text": "unclosed`), the `elem::jsonb` cast throws and PostgreSQL rolls back the entire UPDATE statement. Then the DROP COLUMN and RENAME still run, destroying all concerns data. The migration comment explicitly calls out this "broken state" scenario. Fix: wrap the CASE in a PL/pgSQL block with `EXCEPTION WHEN invalid_text_representation THEN` to fall back to wrapping the element as a plain string.

### Bug 3 — Not idempotent; second run destroys data (lines 34–35)

```sql
ALTER TABLE appointment_prep_contexts DROP COLUMN concerns;
ALTER TABLE appointment_prep_contexts RENAME COLUMN concerns_jsonb TO concerns;
```

Step 1 uses `IF NOT EXISTS`, so re-running adds `concerns_jsonb` again. But Step 3 then drops the already-renamed `concerns` JSONB column (now holding migrated data) and Step 4 fails. Fix: wrap Steps 3–4 in a `DO $$ BEGIN IF EXISTS (concerns_jsonb column) THEN ... END IF; END $$;` guard.

## Proposed Solution

```sql
-- Bug 1 fix: handle empty arrays explicitly
UPDATE appointment_prep_contexts
SET concerns_jsonb = CASE
    WHEN array_length(concerns, 1) IS NULL THEN '[]'::jsonb
    ELSE (SELECT jsonb_agg(...) FROM unnest(concerns) AS elem)
  END
WHERE concerns IS NOT NULL;

-- Bug 2 fix: wrap in PL/pgSQL with exception handling for the CASE expression

-- Bug 3 fix: guard the DROP/RENAME
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'appointment_prep_contexts' AND column_name = 'concerns_jsonb'
  ) THEN
    ALTER TABLE appointment_prep_contexts DROP COLUMN concerns;
    ALTER TABLE appointment_prep_contexts RENAME COLUMN concerns_jsonb TO concerns;
  END IF;
END $$;
```

## Acceptance Criteria

- [ ] Empty array rows (`concerns = '{}'`) become `'[]'::jsonb`, not NULL
- [ ] A row with malformed JSON-like string does not abort the full UPDATE
- [ ] Running the migration twice is safe (no data destruction on second run)
- [ ] Post-deploy verification queries from deployment checklist all pass
- [ ] Add backup step instruction: `CREATE TABLE appointment_prep_contexts_concerns_backup AS SELECT id, concerns FROM appointment_prep_contexts;`
