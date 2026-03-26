---
status: done
priority: p2
issue_id: "079"
tags: [code-review, frontend, design-system, pr-10]
dependencies: ["073"]
---

# Hardcoded hex values in ask/+page.svelte style block defeat the design token system

## Problem Statement

`ask/+page.svelte` has a `<style>` block with global CSS rules for `.citation-ref` and `.message-content a` that use hardcoded hex values (`#0d9478`, `#0f7663`) instead of CSS custom properties. This defeats the design token system — if the primary teal is ever adjusted, these will silently drift out of sync with everything else.

This is also where the WCAG contrast issue (todo #073) lives: the hardcoded `#0d9478` is `primary-600`, which fails 4.5:1 on white.

## Findings

- `ask/+page.svelte` style block line 398: `color: #0d9478` for `.citation-ref` (inline links in AI responses)
- `ask/+page.svelte` style block line 490: `color: #0d9478` for `.message-content a` (links inside rendered markdown)
- Comments in the file acknowledge the intent: `/* primary-600 */`
- `#0f7663` also appears as hover color (`primary-700`)
- These are `:global()` styles needed because the content is injected via `{@html}`
- Identified by kieran-typescript-reviewer

## Proposed Solutions

### Option 1: Use CSS custom properties (Recommended)

Replace hex values with the design token custom properties:

```css
.citation-ref {
  color: var(--color-primary-700); /* was #0d9478 (primary-600, fails WCAG) */
}
.citation-ref:hover {
  color: var(--color-primary-800);
}
.message-content a {
  color: var(--color-primary-700);
}
.message-content a:hover {
  color: var(--color-primary-800);
}
```

Using `primary-700` also resolves the contrast issue from todo #073 (see dependency).

**Pros:** Single source of truth, respects the design token system
**Effort:** Tiny (5 min)
**Risk:** Zero

## Recommended Action

Option 1. Fix in same commit as #073 (contrast fix) since they are in the same location.

## Technical Details

- File: `frontend/src/routes/(app)/ask/+page.svelte` style block lines ~398–495

## Acceptance Criteria

- [ ] No hardcoded hex color values in ask/+page.svelte style block
- [ ] `.citation-ref` and `.message-content a` use `var(--color-primary-*)` tokens
- [ ] Color values match the updated primary text token chosen for #073

## Work Log

- 2026-03-25: Identified by kieran-typescript-reviewer in PR #10 review
2026-03-25: Resolved.
