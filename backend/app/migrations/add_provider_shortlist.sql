-- Migration: add_provider_shortlist
-- Run this in the Supabase SQL editor.
-- Creates a per-user shortlist table for the provider call tracker feature.

CREATE TABLE IF NOT EXISTS provider_shortlist (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
  provider_id     UUID REFERENCES providers(id) ON DELETE CASCADE,
  status          TEXT NOT NULL DEFAULT 'to_call'
                  CHECK (status IN (
                    'to_call', 'called', 'left_voicemail',
                    'booking', 'not_available'
                  )),
  notes           TEXT,
  added_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, provider_id)
);

-- RLS: users can only see and modify their own shortlist entries
ALTER TABLE provider_shortlist ENABLE ROW LEVEL SECURITY;

CREATE POLICY provider_shortlist_user_isolation
  ON provider_shortlist
  FOR ALL
  USING (user_id = auth.uid());
