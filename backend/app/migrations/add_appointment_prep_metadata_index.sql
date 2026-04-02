-- Add composite index for appointment_prep_metadata history queries
-- Supports user filtering + ordering by generated_at

CREATE INDEX IF NOT EXISTS idx_appointment_prep_metadata_user_generated
ON appointment_prep_metadata(user_id, generated_at DESC);

COMMENT ON INDEX idx_appointment_prep_metadata_user_generated IS
  'Supports get_user_prep_history() count + paginated queries';
