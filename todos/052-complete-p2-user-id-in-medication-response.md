---
status: complete
priority: p2
issue_id: "052"
tags: [code-review, security, backend, medications, pii, pr-2]
dependencies: []
---

# Check `MedicationResponse` for `user_id` field — known PII leak pattern

## Problem Statement

New response models scaffolded from DB row shapes frequently include `user_id` accidentally. The client already has identity via the auth token — `user_id` in API responses is unnecessary PII exposure. This is a documented recurring issue in this codebase.

## Findings

- Known pattern: `docs/solutions/security-issues/remove-user-id-from-api-responses.md`
- All new response models need auditing: `MedicationResponse`, `MedicationReferenceResult`
- `user_medications` table has `user_id` column — if `MedicationResponse` has `from_attributes=True`, Pydantic will silently include it unless explicitly excluded
- Per the learnings doc: "When scaffolding any new response model from a DB row shape, explicitly ask 'does the client need user_id?'"

## Proposed Solutions

### Option 1: Audit models and remove `user_id` if present (Recommended)

Check `backend/app/models/medications.py`:
- `MedicationResponse` — should NOT have `user_id`
- `MedicationReferenceResult` — check for `created_by` (which IS a user_id equivalent for user-created entries)

If `user_id` or `created_by` is present in any response model, remove it.

**Effort:** Tiny (audit + potentially remove one field)
**Risk:** None — clients never need this field

## Recommended Action

Audit and remove. The learnings doc makes this a mandatory check for all new response models.

## Technical Details

**Affected files:**
- `backend/app/models/medications.py` — `MedicationResponse`, `MedicationReferenceResult`

## Acceptance Criteria

- [ ] `MedicationResponse` does not include `user_id`
- [ ] `MedicationReferenceResult` does not include `created_by` (or if it does, there's a documented reason)
- [ ] `GET /api/medications` response does not include `user_id` in any item

## Work Log

- 2026-03-18: Identified by learnings-researcher (known pattern `remove-user-id-from-api-responses.md`) in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
