---
status: complete
priority: p2
issue_id: "053"
tags: [code-review, migrations, medications, seed-data, pr-2]
dependencies: []
---

# Seed data contains `'vaginal tablet'` which fails `user_medications.delivery_method` CHECK constraint

## Problem Statement

`seed_medications_reference.sql` uses `'vaginal tablet'` as a `common_forms` value for Vagifem and Endometrin. The `user_medications.delivery_method` column has a CHECK constraint that does not include `'vaginal tablet'`. If the frontend uses `common_forms` to populate the delivery method picker, selecting this value will cause a database constraint violation at insert time.

## Findings

- `backend/app/migrations/seed_medications_reference.sql` lines 56, 78, 84
- `user_medications.delivery_method CHECK` constraint allows: `patch, pill, gel, cream, ring, injection, pellet, spray, troche, sublingual, other`
- `'vaginal tablet'` is not in this list
- `medications_reference.common_forms` is a free-form `TEXT[]` with no constraint — so the seed INSERT succeeds
- But using `'vaginal tablet'` as a delivery method for a `user_medications` INSERT will fail
- Identified by schema-drift-detector

## Proposed Solutions

### Option 1: Replace `'vaginal tablet'` with `'other'` in seed data (Recommended)

Change all `'vaginal tablet'` values in the seed file to `'other'`.

**Pros:** Immediate fix, no schema changes needed
**Effort:** Tiny
**Risk:** None

### Option 2: Add `'vaginal_tablet'` to the CHECK constraint and `DeliveryMethod` Literal

Update the CHECK constraint in the migration, the `DeliveryMethod` Literal in `models/medications.py`, and the seed data consistently.

**Pros:** More accurate delivery method representation
**Effort:** Small — requires new migration to alter the constraint
**Risk:** Low — additive change

## Recommended Action

Option 1 for now (quickest fix). Option 2 can be a follow-up if vaginal tablets are a common delivery method worth tracking separately.

## Technical Details

**Affected files:**
- `backend/app/migrations/seed_medications_reference.sql` lines 56, 78, 84

## Acceptance Criteria

- [ ] No `'vaginal tablet'` values remain in `seed_medications_reference.sql`
- [ ] All `common_forms` values in seed data are valid `delivery_method` CHECK values or `'other'`

## Work Log

- 2026-03-18: Identified by schema-drift-detector in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
