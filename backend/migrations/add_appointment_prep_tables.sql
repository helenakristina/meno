-- Migration: Add Appointment Prep Flow Tables
-- Description: Creates tables for storing appointment prep context, narratives, and outputs
-- Created: 2026-03-05
-- Note: Run this in Supabase SQL Editor after applying migrations to database

-- ============================================================================
-- Table: appointment_prep_contexts
-- Purpose: Stores the initial context selections from Step 1 (appointment type, goal, dismissal)
-- ============================================================================

CREATE TABLE IF NOT EXISTS appointment_prep_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    appointment_type TEXT NOT NULL CHECK (appointment_type IN ('new_provider', 'established_relationship')),
    goal TEXT NOT NULL CHECK (goal IN ('understand_where_i_am', 'discuss_starting_hrt', 'evaluate_current_treatment', 'address_specific_symptom')),
    dismissed_before TEXT NOT NULL CHECK (dismissed_before IN ('no', 'once_or_twice', 'multiple_times')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_appointment_prep_contexts_user_id ON appointment_prep_contexts(user_id, created_at DESC);

-- Comment on table
COMMENT ON TABLE appointment_prep_contexts IS 'Initial context selections from Step 1 of Appointment Prep flow. Shapes tone and content of all generated outputs.';
COMMENT ON COLUMN appointment_prep_contexts.appointment_type IS 'Type of appointment: new_provider or established_relationship';
COMMENT ON COLUMN appointment_prep_contexts.goal IS 'Primary goal: understand_where_i_am, discuss_starting_hrt, evaluate_current_treatment, address_specific_symptom';
COMMENT ON COLUMN appointment_prep_contexts.dismissed_before IS 'Prior dismissal experience: no, once_or_twice, multiple_times';

-- ============================================================================
-- Table: appointment_prep_outputs
-- Purpose: Stores the complete appointment prep data including narrative, concerns, and final outputs
-- ============================================================================

CREATE TABLE IF NOT EXISTS appointment_prep_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    context_id UUID NOT NULL REFERENCES appointment_prep_contexts(id) ON DELETE CASCADE,
    narrative TEXT,
    concerns TEXT[] DEFAULT '{}',
    provider_summary_content TEXT,
    provider_summary_generated_at TIMESTAMPTZ,
    personal_cheat_sheet_content TEXT,
    personal_cheat_sheet_generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_appointment_prep_outputs_user_id ON appointment_prep_outputs(user_id, created_at DESC);

-- Index for lookups by context_id
CREATE INDEX IF NOT EXISTS idx_appointment_prep_outputs_context_id ON appointment_prep_outputs(context_id);

-- Comment on table
COMMENT ON TABLE appointment_prep_outputs IS 'Complete appointment prep data including narrative (Step 2), prioritized concerns (Step 3), and final outputs (Step 5).';
COMMENT ON COLUMN appointment_prep_outputs.narrative IS 'LLM-generated narrative summary of symptoms from Step 2, editable by user';
COMMENT ON COLUMN appointment_prep_outputs.concerns IS 'Prioritized list of concerns from Step 3';
COMMENT ON COLUMN appointment_prep_outputs.provider_summary_content IS 'One-page clinical overview generated in Step 5, designed to be shared with provider';
COMMENT ON COLUMN appointment_prep_outputs.personal_cheat_sheet_content IS 'Prioritized concerns and conversation anchors from Step 5, private to user';

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on both tables
ALTER TABLE appointment_prep_contexts ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointment_prep_outputs ENABLE ROW LEVEL SECURITY;

-- appointment_prep_contexts: Users can only select/insert/update/delete their own records
CREATE POLICY "Users can view their own contexts" ON appointment_prep_contexts
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own contexts" ON appointment_prep_contexts
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own contexts" ON appointment_prep_contexts
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own contexts" ON appointment_prep_contexts
    FOR DELETE
    USING (auth.uid() = user_id);

-- appointment_prep_outputs: Users can only select/insert/update/delete their own records
CREATE POLICY "Users can view their own prep outputs" ON appointment_prep_outputs
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own prep outputs" ON appointment_prep_outputs
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own prep outputs" ON appointment_prep_outputs
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own prep outputs" ON appointment_prep_outputs
    FOR DELETE
    USING (auth.uid() = user_id);
