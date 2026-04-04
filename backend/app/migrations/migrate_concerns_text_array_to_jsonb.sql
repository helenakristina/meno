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

-- Step 1: Add a temporary JSONB column
ALTER TABLE appointment_prep_contexts
  ADD COLUMN IF NOT EXISTS concerns_jsonb JSONB DEFAULT NULL;

-- Step 2: Back-fill — convert each TEXT[] element to a Concern JSONB object.
--   Each element is either a plain string or a JSON-stringified object.
--   We try to parse it as JSON; if it already has a "text" key we use it directly,
--   otherwise we wrap it: {"text": element, "comment": null}.
UPDATE appointment_prep_contexts
SET concerns_jsonb = (
  SELECT jsonb_agg(
    CASE
      WHEN elem ~ '^\s*\{' AND (elem::jsonb) ? 'text'
        THEN elem::jsonb                              -- already a {"text":...} object
      ELSE jsonb_build_object('text', elem, 'comment', NULL)  -- plain string → wrap it
    END
  )
  FROM unnest(concerns) AS elem
)
WHERE concerns IS NOT NULL AND array_length(concerns, 1) > 0;

-- Step 3: Drop the old TEXT[] column and rename the new one
ALTER TABLE appointment_prep_contexts DROP COLUMN concerns;
ALTER TABLE appointment_prep_contexts RENAME COLUMN concerns_jsonb TO concerns;

COMMENT ON COLUMN appointment_prep_contexts.concerns IS 'Prioritized concerns from Step 3 as JSONB array: [{text: string, comment: string|null}]';
