-- Add urgent_symptom column to capture which symptom the user marks as urgent
-- This is only used when goal is 'urgent_symptom'

ALTER TABLE appointment_prep_contexts
ADD COLUMN urgent_symptom TEXT DEFAULT NULL;

-- Add index for querying by urgent_symptom (optional, low priority)
-- CREATE INDEX idx_urgent_symptom ON appointment_prep_contexts(urgent_symptom) WHERE goal = 'urgent_symptom';
