-- Rollback: remove frequency_stats and cooccurrence_stats columns from appointment_prep_contexts
-- These columns were added by add_frequency_stats_to_appointment_prep_contexts.sql
-- to cache pre-computed stats for Step 2 (generate_narrative) and Step 5 (PDF generation)

ALTER TABLE appointment_prep_contexts
DROP COLUMN IF EXISTS frequency_stats;

ALTER TABLE appointment_prep_contexts
DROP COLUMN IF EXISTS cooccurrence_stats;
