---
status: complete
priority: p2
issue_id: "048"
tags: [code-review, frontend, accessibility, settings, medications, pr-2]
dependencies: []
---

# `<label>` wrapping `<button role="switch">` — invalid HTML, breaks screen readers

## Problem Statement

The MHT tracking toggle in `settings/+page.svelte` wraps a `<button role="switch">` in a `<label>` element. `<label>` is only for labelable form elements (`input`, `select`, `textarea`). Wrapping a `<button>` produces undefined behavior across assistive technologies.

## Findings

- `frontend/src/routes/(app)/settings/+page.svelte` lines 215–235, 252–272
- Both the "Enable cycle tracking" and "Enable MHT tracking" toggle rows have this pattern
- The button already has `aria-label="Enable MHT tracking"` / `aria-label="Enable cycle tracking"` — the `<label>` wrapper is redundant and invalid
- Identified by TypeScript reviewer (WCAG 2.1 AA violation)

## Proposed Solutions

### Option 1: Replace `<label>` with `<div>` (Recommended)

```svelte
<!-- Before -->
<label class="flex cursor-pointer items-center gap-3" ...>

<!-- After -->
<div class="flex cursor-pointer items-center gap-3" ...>
```

The button's `aria-label` already provides the accessible name. The `onclick` handler is on the button itself.

**Pros:** Valid HTML, accessible, zero behavior change
**Effort:** Tiny (s/label/div/)
**Risk:** None

## Recommended Action

Option 1 — the fix is a two-character change per toggle row.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/settings/+page.svelte` lines ~215, ~252 (two toggle rows)

Note: the pre-existing cycle tracking toggle row in the same file has the same pattern — fix both while here.

## Acceptance Criteria

- [ ] Neither toggle row uses `<label>` wrapping a `<button>`
- [ ] Both toggles still function correctly
- [ ] `aria-label` attributes remain on the buttons

## Work Log

- 2026-03-18: Identified by TypeScript reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
