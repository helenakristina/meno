-- Migration: add_period_tracking
-- Run this in the Supabase SQL editor.
-- Adds period tracking preferences to users, and creates period_logs and cycle_analysis tables.

-- Add period tracking preferences to users
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS period_tracking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS has_uterus BOOLEAN;  -- NULL = not disclosed

-- period_logs: one row per period occurrence logged by a user
CREATE TABLE IF NOT EXISTS period_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  period_start    DATE NOT NULL,
  period_end      DATE,
  flow_level      TEXT CHECK (flow_level IN ('spotting', 'light', 'medium', 'heavy')),
  notes           TEXT,
  cycle_length    INTEGER,  -- days since previous period_start, calculated server-side
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE period_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY period_logs_user_isolation
  ON period_logs
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Index for efficient date-range queries (used by GET /api/period/logs)
CREATE INDEX IF NOT EXISTS idx_period_logs_user_date
  ON period_logs (user_id, period_start DESC);

-- Prevent duplicate logs for the same period start date per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_period_logs_user_start
  ON period_logs (user_id, period_start);

-- cycle_analysis: one row per user, upserted after each log create/delete
CREATE TABLE IF NOT EXISTS cycle_analysis (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  average_cycle_length        DECIMAL,
  cycle_variability           DECIMAL,  -- standard deviation; high variability = perimenopause indicator
  months_since_last_period    INTEGER,
  inferred_stage              TEXT CHECK (inferred_stage IN ('perimenopause', 'menopause', 'post-menopause')),
  calculated_at               TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE cycle_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY cycle_analysis_user_isolation
  ON cycle_analysis
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Enforce one row per user (used by upsert pattern in PeriodRepository)
CREATE UNIQUE INDEX IF NOT EXISTS idx_cycle_analysis_user
  ON cycle_analysis (user_id);
