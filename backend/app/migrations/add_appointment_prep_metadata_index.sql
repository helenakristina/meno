-- Add composite index for appointment_prep_metadata history queries
-- Supports user filtering + ordering by generated_at

-- Remove the pre-existing index idx_appointment_prep_metadata_user_id which only has user_id.
-- This is redundant since the new composite index (user_id, generated_at DESC) covers all queries
-- that the single-column index would handle, eliminating 2x write overhead.
DROP INDEX IF EXISTS idx_appointment_prep_metadata_user_id;

CREATE INDEX IF NOT EXISTS idx_appointment_prep_metadata_user_generated
ON appointment_prep_metadata(user_id, generated_at DESC);

COMMENT ON INDEX idx_appointment_prep_metadata_user_generated IS
  'Supports get_user_prep_history() count + paginated queries';
