---
status: pending
priority: p2
issue_id: "034"
tags: [code-review, accessibility, frontend, wcag]
dependencies: []
---

# Calendar prev/next month buttons are 36×36px — WCAG requires 44×44px

## Problem Statement

`PeriodCalendar.svelte` nav buttons use `h-9 w-9` (36×36px). Project standard and WCAG 2.1 AA require interactive elements to be at minimum 44×44px.

## Findings

- **File**: `frontend/src/lib/components/period/PeriodCalendar.svelte` (prev/next month nav buttons)
- `h-9 w-9` = 36px × 36px — 8px short on both axes

## Proposed Solution

Change `h-9 w-9` to `h-11 w-11` (44×44px) on the prev/next buttons.

## Acceptance Criteria
- [ ] Prev/next month buttons are ≥ 44×44px
- [ ] Visual appearance is appropriate at new size
