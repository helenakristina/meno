-- Migration: MHT Medication Tracking
-- Adds mht_tracking_enabled to users, creates medications_reference and
-- user_medications tables, RLS policies, indexes, and an atomic RPC function
-- for changing a medication dose/method.

-- ============================================================
-- 1. Feature toggle on users table
-- ============================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS mht_tracking_enabled BOOLEAN DEFAULT FALSE;

-- ============================================================
-- 2. medications_reference — system-curated + user-created
-- ============================================================
CREATE TABLE IF NOT EXISTS medications_reference (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name       TEXT,
    generic_name     TEXT NOT NULL,
    hormone_type     TEXT NOT NULL CHECK (hormone_type IN (
                       'estrogen', 'progesterone', 'progestin',
                       'testosterone', 'combination'
                     )),
    common_forms     TEXT[] DEFAULT '{}',
    common_doses     TEXT[] DEFAULT '{}',
    notes            TEXT,
    is_user_created  BOOLEAN DEFAULT FALSE,
    created_by       UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE medications_reference IS
    'System-curated and user-created MHT medication reference. '
    'System entries (is_user_created=FALSE) are readable by all authenticated users. '
    'User-created entries are RLS-scoped to the creating user only to prevent '
    'typo propagation and prompt injection via user-controlled medication names.';

-- ============================================================
-- 3. user_medications — timeline model (one row = one stint)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_medications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    medication_ref_id   UUID REFERENCES medications_reference(id) ON DELETE SET NULL,
    medication_name     TEXT NOT NULL,           -- denormalized from reference at creation
    dose                TEXT NOT NULL,
    delivery_method     TEXT NOT NULL CHECK (delivery_method IN (
                          'patch', 'pill', 'gel', 'cream', 'ring',
                          'injection', 'pellet', 'spray', 'troche',
                          'sublingual', 'other'
                        )),
    frequency           TEXT,
    start_date          DATE NOT NULL,
    end_date            DATE,                    -- NULL = currently active
    previous_entry_id   UUID REFERENCES user_medications(id) ON DELETE SET NULL,
    notes               TEXT CHECK (char_length(notes) <= 1000),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT end_date_after_start CHECK (end_date IS NULL OR end_date >= start_date)
);

COMMENT ON TABLE user_medications IS
    'Timeline of user MHT medication stints. Each row represents one medication '
    'at a specific dose/method for a time window. Dose or delivery method changes '
    'create a new row; the old row gets end_date set. previous_entry_id links '
    'the new row back to the one it replaced. end_date IS NULL = currently active.';

-- ============================================================
-- 4. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_user_medications_user_start
    ON user_medications(user_id, start_date DESC);

CREATE INDEX IF NOT EXISTS idx_user_medications_active
    ON user_medications(user_id) WHERE end_date IS NULL;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_medications_reference_search
    ON medications_reference
    USING gin((coalesce(brand_name, '') || ' ' || generic_name) gin_trgm_ops);

-- ============================================================
-- 5. RLS — medications_reference
-- ============================================================
ALTER TABLE medications_reference ENABLE ROW LEVEL SECURITY;

-- Any authenticated user can read system entries
CREATE POLICY "Anyone reads system medication entries"
    ON medications_reference FOR SELECT
    USING (is_user_created = FALSE);

-- Creator can read their own entries
CREATE POLICY "Users read own created entries"
    ON medications_reference FOR SELECT
    USING (is_user_created = TRUE AND created_by = auth.uid());

-- Creator can insert their own entries
CREATE POLICY "Users insert own medication entries"
    ON medications_reference FOR INSERT
    WITH CHECK (is_user_created = TRUE AND created_by = auth.uid());

-- Creator can update their own entries
CREATE POLICY "Users update own created entries"
    ON medications_reference FOR UPDATE
    USING (is_user_created = TRUE AND created_by = auth.uid());

-- Creator can delete their own entries
CREATE POLICY "Users delete own created entries"
    ON medications_reference FOR DELETE
    USING (is_user_created = TRUE AND created_by = auth.uid());

-- ============================================================
-- 6. RLS — user_medications
-- ============================================================
ALTER TABLE user_medications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own medications"
    ON user_medications FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users insert own medications"
    ON user_medications FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own medications"
    ON user_medications FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users delete own medications"
    ON user_medications FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 7. Atomic dose-change RPC function
-- Atomically ends the current stint and creates the new one.
-- Both writes happen in the same transaction — if the INSERT
-- fails the UPDATE rolls back automatically.
-- ============================================================
CREATE OR REPLACE FUNCTION change_medication_dose(
    p_old_id            UUID,
    p_user_id           UUID,
    p_effective_date    DATE,
    p_new_dose          TEXT,
    p_new_delivery      TEXT,
    p_new_frequency     TEXT,
    p_new_notes         TEXT,
    p_ref_id            UUID,
    p_medication_name   TEXT
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_old_start DATE;
    v_new_id    UUID;
BEGIN
    -- Verify ownership and fetch start_date in one query
    SELECT start_date INTO v_old_start
    FROM user_medications
    WHERE id = p_old_id AND user_id = p_user_id AND end_date IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'medication_not_found';
    END IF;

    -- effective_date must be strictly after the old stint's start_date
    IF p_effective_date <= v_old_start THEN
        RAISE EXCEPTION 'effective_date_before_start';
    END IF;

    -- End the old stint (end_date = effective_date - 1 day)
    UPDATE user_medications
    SET    end_date   = p_effective_date - INTERVAL '1 day',
           updated_at = NOW()
    WHERE  id = p_old_id AND user_id = p_user_id;

    -- Create the new stint
    INSERT INTO user_medications (
        user_id, medication_ref_id, medication_name,
        dose, delivery_method, frequency,
        start_date, notes, previous_entry_id
    ) VALUES (
        p_user_id, p_ref_id, p_medication_name,
        p_new_dose, p_new_delivery, p_new_frequency,
        p_effective_date, p_new_notes, p_old_id
    )
    RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$;
