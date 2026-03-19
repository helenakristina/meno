---
status: complete
priority: p3
issue_id: "059"
tags: [code-review, frontend, ux, medications, pr-2]
dependencies: []
---

# Nav label `'MHT'` is opaque — prefer `'Medications'` for clarity

## Problem Statement

The navigation link for the medication tracking section is labelled `'MHT'` — an abbreviation not expanded anywhere in the nav context. All other nav labels use plain English words (`'Cycles'`, `'Dashboard'`, etc.). New users unfamiliar with the acronym won't know what this section is.

## Findings

- `frontend/src/routes/(app)/+layout.svelte` line 77
- `'MHT'` = Menopausal Hormone Therapy — domain terminology, not universally known
- All other nav items use clear plain-language labels
- Identified by TypeScript reviewer and agent-native reviewer

## Proposed Solutions

### Option 1: Change to `'Medications'` (Recommended)

**Pros:** Immediately understandable, consistent with other nav labels
**Effort:** Tiny (1 word change)
**Risk:** None

### Option 2: Change to `'MHT Tracker'` or `'Hormones'`

If the intent is to emphasize the MHT-specific nature while still being approachable.

## Recommended Action

`'Medications'` — simple, clear, consistent.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/+layout.svelte` line 77

## Acceptance Criteria

- [ ] Nav label uses a plain-English word instead of the `'MHT'` abbreviation

## Work Log

- 2026-03-18: Identified by TypeScript reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
