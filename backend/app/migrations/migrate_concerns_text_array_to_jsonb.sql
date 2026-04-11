-- Migrate concerns column from TEXT[] to JSONB on appointment_prep_contexts
--
-- Phase 5 changed concerns from string[] to Concern[] objects ({text, comment}).
-- The column was originally TEXT[] (added in add_appointment_scenarios_column.sql).
-- This migration converts the type and back-fills any existing rows.
--
-- Existing rows may contain:
--   a) NULL                  → stays NULL
--   b) TEXT[] of plain strings  → converted to [{"text": "...", "comment": null}, ...]
--   c) TEXT[] of JSON-stringified objects (the broken state) → parsed and stored as proper JSONB
--   d) Empty TEXT[] {}       → converted to '[]'::jsonb
--
-- RECOMMENDED: Take a backup before running this migration:
--   CREATE TABLE appointment_prep_contexts_concerns_backup AS SELECT id, concerns FROM appointment_prep_contexts;

-- Step 1: Add a temporary JSONB column
ALTER TABLE appointment_prep_contexts
  ADD COLUMN IF NOT EXISTS concerns_jsonb JSONB DEFAULT NULL;

-- Step 2: Back-fill — convert each TEXT[] element to a Concern JSONB object.
--
--   Bug fixes applied here:
--     a) Empty arrays (concerns = '{}') now produce '[]'::jsonb instead of NULL.
--        The original WHERE guard used array_length(concerns, 1) > 0 which returns
--        NULL (not 0) for '{}', silently dropping empty-array rows from the UPDATE.
--     b) Malformed JSON strings (e.g. '{"text": "unclosed') no longer abort the
--        entire UPDATE. Each element is converted inside a PL/pgSQL DO block with
--        an EXCEPTION handler so a bad element falls back to plain-string wrapping
--        instead of rolling back all rows.
--     c) The DROP/RENAME in Step 3 is now guarded by an IF EXISTS check, making
--        the migration safe to run more than once.

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
    -- Handle empty array: produce '[]'::jsonb
    IF array_length(rec.concerns, 1) IS NULL THEN
      UPDATE appointment_prep_contexts
        SET concerns_jsonb = '[]'::jsonb
        WHERE id = rec.id;
      CONTINUE;
    END IF;

    -- Build the JSONB array element by element with per-element exception handling
    result := '[]'::jsonb;
    FOREACH elem IN ARRAY rec.concerns LOOP
      BEGIN
        IF elem ~ '^\s*\{' THEN
          -- Looks like a JSON object — try to parse it
          elem_jsonb := elem::jsonb;
          IF elem_jsonb ? 'text' THEN
            -- Already a {"text": ...} object; use it directly
            result := result || jsonb_build_array(elem_jsonb);
          ELSE
            -- JSON object but no "text" key — wrap it as a plain string
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
        WHEN invalid_text_representation THEN
          -- Malformed JSON-like string: fall back to treating as plain string
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

-- Step 3: Drop the old TEXT[] column and rename the new one.
--   Guarded by IF EXISTS so re-running the migration is safe and will not drop
--   the already-migrated JSONB concerns column.
DO $$
BEGIN
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

COMMENT ON COLUMN appointment_prep_contexts.concerns IS 'Prioritized concerns from Step 3 as JSONB array: [{text: string, comment: string|null}]';
