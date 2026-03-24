-- Migration: add insurance preference columns to users table
-- Run manually in Supabase SQL editor — do not execute programmatically.
-- Applied: 2026-02-21

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS insurance_type TEXT
    CHECK (insurance_type IN (
      'private', 'medicare', 'medicaid', 'self_pay', 'other'
    )),
  ADD COLUMN IF NOT EXISTS insurance_plan_name TEXT;
