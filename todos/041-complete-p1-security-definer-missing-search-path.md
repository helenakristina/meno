---
status: complete
priority: p1
issue_id: "041"
tags: [code-review, security, migrations, postgres, medications, pr-2]
dependencies: []
---

# `SECURITY DEFINER` function missing `search_path` lock

## Problem Statement

The `change_medication_dose` Postgres function is declared `SECURITY DEFINER` (runs with owner's privileges) but has no `SET search_path` clause. Without it, any schema placed earlier in `search_path` can shadow the `user_medications` table or functions, enabling a schema-injection attack.

## Findings

- `backend/app/migrations/add_mht_medication_tracking.sql` lines 136–188
- Function declared: `LANGUAGE plpgsql SECURITY DEFINER AS $$...`
- Missing: `SET search_path = public, pg_temp`
- Function body uses unqualified table name `user_medications` — resolved via `search_path` at call time
- Standard Postgres/Supabase hardening requirement for any `SECURITY DEFINER` function
- Also identified by schema-drift-detector

## Proposed Solutions

### Option 1: Add `SET search_path` to the function definition (Recommended)

```sql
CREATE OR REPLACE FUNCTION change_medication_dose(...)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
```

**Pros:** Standard hardening, one-line fix
**Effort:** Small
**Risk:** None — this only restricts the search path to what it should already be

## Recommended Action

Option 1 — apply the fix to the migration file.

## Technical Details

**Affected files:**
- `backend/app/migrations/add_mht_medication_tracking.sql` line ~147

## Acceptance Criteria

- [ ] `change_medication_dose` function definition includes `SET search_path = public, pg_temp`
- [ ] Migration runs cleanly after the change

## Work Log

- 2026-03-18: Identified by security-sentinel and schema-drift-detector in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready

## Resources

- PR #2: feat/mht-medication-tracking
- Postgres docs: SECURITY DEFINER and search_path
