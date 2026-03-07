-- Update AppointmentGoal check constraint to new enum values
-- This migration updates existing rows AND the constraint

-- First, migrate existing data to new enum values
UPDATE appointment_prep_contexts
SET goal = CASE
    WHEN goal = 'understand_where_i_am' THEN 'assess_status'
    WHEN goal = 'discuss_starting_hrt' THEN 'explore_hrt'
    WHEN goal = 'evaluate_current_treatment' THEN 'optimize_current_treatment'
    WHEN goal = 'address_specific_symptom' THEN 'urgent_symptom'
    ELSE goal
END;

-- Drop the old constraint
ALTER TABLE appointment_prep_contexts
DROP CONSTRAINT IF EXISTS appointment_prep_contexts_goal_check;

-- Add the new constraint with updated values
ALTER TABLE appointment_prep_contexts
ADD CONSTRAINT appointment_prep_contexts_goal_check
CHECK (goal IN ('assess_status', 'explore_hrt', 'optimize_current_treatment', 'urgent_symptom'));
