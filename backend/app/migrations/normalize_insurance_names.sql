-- One-time cleanup: normalize existing "Commercial Insurance" values
-- to "Private Insurance" in the providers table.
-- Run once in the Supabase SQL editor after deploying this change.
-- Safe to re-run — UPDATE only affects rows that still contain the old value.

UPDATE providers
SET insurance_accepted = array_replace(
    insurance_accepted,
    'Commercial Insurance',
    'Private Insurance'
)
WHERE 'Commercial Insurance' = ANY(insurance_accepted);
