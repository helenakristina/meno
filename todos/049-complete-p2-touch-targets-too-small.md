---
status: complete
priority: p2
issue_id: "049"
tags: [code-review, frontend, accessibility, medications, wcag, pr-2]
dependencies: []
---

# Medication card action links below 44px WCAG AA touch target minimum

## Problem Statement

The "Impact" and "View" action links on medication cards in `medications/+page.svelte` use `px-3 py-1.5`, rendering at approximately 28px height. WCAG 2.1 AA requires all interactive touch targets to be at minimum 44×44px.

## Findings

- `frontend/src/routes/(app)/medications/+page.svelte` lines 105–116, 142–146
- `py-1.5` = 12px top + 12px bottom + line-height ≈ 28px total height
- These are the primary interaction points for each medication card on mobile (375px viewport)
- Also affects the "Add medication" button padding in the empty state
- WCAG 2.1 Success Criterion 2.5.5 (AAA) recommends 44px; AA requires sufficient target size

## Proposed Solutions

### Option 1: Increase padding to meet minimum (Recommended)

Change `py-1.5` to `py-2.5` on action links, or add `min-h-[44px]` with `flex items-center`:

```svelte
<!-- Before -->
<a href="..." class="... px-3 py-1.5 ...">

<!-- After -->
<a href="..." class="... px-3 py-2.5 min-h-[44px] flex items-center ...">
```

**Pros:** WCAG AA compliant, better mobile UX
**Effort:** Tiny
**Risk:** Minor visual change — cards become slightly taller

## Recommended Action

Option 1 — `min-h-[44px] flex items-center` is the safest approach (won't add unnecessary padding on desktop while ensuring minimum touch size).

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/medications/+page.svelte` lines ~105–116, ~142–146

## Acceptance Criteria

- [ ] "Impact" and "View" links have `min-h-[44px]`
- [ ] Touch targets verified to be ≥ 44×44px in mobile viewport (375px)

## Work Log

- 2026-03-18: Identified by TypeScript reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
