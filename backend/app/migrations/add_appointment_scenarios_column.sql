-- Add scenarios column to appointment_prep_contexts
-- This stores the scenario cards generated in Step 4 as JSON

ALTER TABLE appointment_prep_contexts
ADD COLUMN scenarios JSONB DEFAULT NULL;

-- Add index for query performance
CREATE INDEX idx_appointment_scenarios ON appointment_prep_contexts USING GIN (scenarios);

-- Add concerns column if not already present (Step 3 data)
ALTER TABLE appointment_prep_contexts
ADD COLUMN IF NOT EXISTS concerns TEXT[] DEFAULT NULL;
