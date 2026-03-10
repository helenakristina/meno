-- Track generated appointment prep PDFs for user history
CREATE TABLE IF NOT EXISTS appointment_prep_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    appointment_id UUID NOT NULL REFERENCES appointment_prep_contexts(id) ON DELETE CASCADE,
    provider_summary_path TEXT NOT NULL,
    personal_cheatsheet_path TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX idx_appointment_prep_metadata_user_id ON appointment_prep_metadata(user_id, generated_at DESC);
CREATE INDEX idx_appointment_prep_metadata_appointment_id ON appointment_prep_metadata(appointment_id);

-- RLS: Users can only see their own metadata
ALTER TABLE appointment_prep_metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own appointment prep metadata"
ON appointment_prep_metadata FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own appointment prep metadata"
ON appointment_prep_metadata FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own appointment prep metadata"
ON appointment_prep_metadata FOR DELETE
USING (auth.uid() = user_id);

COMMENT ON TABLE appointment_prep_metadata IS 'Tracks generated appointment prep PDFs for user history and retrieval';
