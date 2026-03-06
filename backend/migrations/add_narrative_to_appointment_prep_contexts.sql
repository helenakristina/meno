-- Add narrative column to appointment_prep_contexts
-- The save_narrative() repository method writes to this table but the column was missing.

ALTER TABLE appointment_prep_contexts
ADD COLUMN IF NOT EXISTS narrative TEXT DEFAULT NULL;

COMMENT ON COLUMN appointment_prep_contexts.narrative IS 'LLM-generated narrative summary of symptoms from Step 2, editable by user';
