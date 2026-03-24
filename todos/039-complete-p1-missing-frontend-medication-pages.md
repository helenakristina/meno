---
status: complete
priority: p1
issue_id: "039"
tags: [code-review, frontend, svelte5, medications, pr-2]
dependencies: []
---

# Missing frontend sub-pages — medication list links go to 404

## Problem Statement

`/medications/+page.svelte` renders links to three routes that have no SvelteKit `+page.svelte` files. Every action beyond viewing the list is broken for users. The backend endpoints are fully implemented and working — only the UI pages are missing.

## Findings

- `/medications/add` (line 63, 82) — "Add medication" button and empty-state link both 404
- `/medications/{id}` (lines 112, 143) — "View" link on every card 404
- `/medications/{id}/impact` (line 106) — "Impact" link on every current medication card 404
- Backend endpoints exist and are functional: `POST /api/medications`, `GET /api/medications/{id}`, `GET /api/medications/{id}/symptom-comparison`
- Agent-native reviewer confirmed: 4 of 9 backend capabilities have no working UI

## Proposed Solutions

### Option 1: Add the three missing pages (Recommended)

Create:
- `frontend/src/routes/(app)/medications/add/+page.svelte` — form to add a medication (search reference, enter dose/form/frequency, start date)
- `frontend/src/routes/(app)/medications/[id]/+page.svelte` — medication detail with update form, dose-change flow
- `frontend/src/routes/(app)/medications/[id]/impact/+page.svelte` — renders `GET /api/medications/{id}/symptom-comparison` data

**Pros:** Feature is complete, users can add/view/update/change-dose/delete
**Effort:** Large
**Risk:** Low — API is ready

### Option 2: Redirect unimplemented links to `/settings` with a "coming soon" notice

**Pros:** Unblocks merge quickly
**Cons:** Users can't use the feature, defeats the PR's purpose
**Effort:** Small
**Risk:** Low

## Recommended Action

Option 1 — the backend is ready and the feature is the stated goal of the PR. The list page is scaffolded and waiting.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/medications/add/+page.svelte` (create)
- `frontend/src/routes/(app)/medications/[id]/+page.svelte` (create)
- `frontend/src/routes/(app)/medications/[id]/impact/+page.svelte` (create)

**Components needed:**
- Medication form (reusable for add + edit)
- Symptom comparison chart/table

## Acceptance Criteria

- [ ] User can navigate to `/medications/add`, fill out the form, and create a medication
- [ ] User can navigate to `/medications/{id}` and see medication details
- [ ] User can update a medication or change dose from the detail page
- [ ] User can delete a medication from the detail page
- [ ] User can navigate to `/medications/{id}/impact` and see before/after symptom comparison

## Work Log

- 2026-03-18: Identified by agent-native-reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready

## Resources

- PR #2: feat/mht-medication-tracking
- Backend: `backend/app/api/routes/medications.py`
- Symptom comparison endpoint: `GET /api/medications/{id}/symptom-comparison`
