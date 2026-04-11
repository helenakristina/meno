-- Add qualitative context columns to appointment_prep_contexts
-- Phase 5: Step 3.5 captures what the user has tried, their specific ask, and clinical history.
-- These columns feed provider summary and cheat sheet prompts.

ALTER TABLE appointment_prep_contexts
  ADD COLUMN IF NOT EXISTS what_have_you_tried   TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS specific_ask          TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS history_clotting_risk TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS history_breast_cancer TEXT DEFAULT NULL;

-- Constrain enum-style columns to valid values only
ALTER TABLE appointment_prep_contexts
  ADD CONSTRAINT chk_history_clotting_risk
    CHECK (history_clotting_risk IS NULL OR history_clotting_risk IN ('yes', 'no', 'not_sure')),
  ADD CONSTRAINT chk_history_breast_cancer
    CHECK (history_breast_cancer IS NULL OR history_breast_cancer IN ('yes', 'no', 'not_sure'));

COMMENT ON COLUMN appointment_prep_contexts.what_have_you_tried IS 'Treatments/lifestyle changes the user has already tried (Step 3.5 free text, max 500 chars)';
COMMENT ON COLUMN appointment_prep_contexts.specific_ask IS 'What the user specifically wants from this appointment (Step 3.5 free text, max 300 chars)';
COMMENT ON COLUMN appointment_prep_contexts.history_clotting_risk IS 'Personal/family history of blood clots or clotting disorders: yes | no | not_sure | NULL';
COMMENT ON COLUMN appointment_prep_contexts.history_breast_cancer IS 'Personal/family history of breast cancer: yes | no | not_sure | NULL';
