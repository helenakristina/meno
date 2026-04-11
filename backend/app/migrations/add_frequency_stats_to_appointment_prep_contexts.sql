-- Add frequency_stats and cooccurrence_stats columns to appointment_prep_contexts
-- Step 2 (generate_narrative) saves pre-computed stats so Step 5 (PDF generation)
-- can reuse them without re-querying symptom logs.

ALTER TABLE appointment_prep_contexts
ADD COLUMN IF NOT EXISTS frequency_stats JSONB DEFAULT NULL;

ALTER TABLE appointment_prep_contexts
ADD COLUMN IF NOT EXISTS cooccurrence_stats JSONB DEFAULT NULL;

COMMENT ON COLUMN appointment_prep_contexts.frequency_stats IS 'Serialized list of SymptomFrequency dicts computed at Step 2, reused by Step 5 PDF generation';
COMMENT ON COLUMN appointment_prep_contexts.cooccurrence_stats IS 'Serialized list of SymptomPair dicts computed at Step 2, reused by Step 5 PDF generation';
