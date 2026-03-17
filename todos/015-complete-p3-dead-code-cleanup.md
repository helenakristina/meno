---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, frontend, cleanup]
dependencies: []
---

# Remove dead code: `parseDateString`, `getJourneyStageLabel`, unused `CalendarDate` import

## Problem Statement

Two helper functions are defined but never called in the frontend:

1. `parseDateString` in `period/+page.svelte:50-53` — defined with `CalendarDate` import, never used
2. `getJourneyStageLabel` in `settings/+page.svelte:111-113` — defined, never used

These are dead code that add confusion about what the page is doing.

## Findings

- `frontend/src/routes/(app)/period/+page.svelte:3` — `CalendarDate` imported solely for `parseDateString`
- `frontend/src/routes/(app)/period/+page.svelte:50-53` — `parseDateString` defined, 0 references
- `frontend/src/routes/(app)/settings/+page.svelte:111-113` — `getJourneyStageLabel` defined, 0 references
- Code simplicity reviewer flagged both

## Proposed Solutions

### Option 1: Delete both functions and the CalendarDate import

**Approach:** Remove `parseDateString` (lines 50-53), `CalendarDate` import (line 3 token), and `getJourneyStageLabel` (lines 111-113).

**Effort:** 5 minutes

**Risk:** None

## Recommended Action

Option 1. Pure cleanup.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/period/+page.svelte:3,50-53`
- `frontend/src/routes/(app)/settings/+page.svelte:111-113`

## Acceptance Criteria

- [ ] `parseDateString` removed from period page
- [ ] `CalendarDate` import removed from period page
- [ ] `getJourneyStageLabel` removed from settings page
- [ ] No TypeScript errors after removal

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
