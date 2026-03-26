---
status: done
priority: p2
issue_id: "078"
tags: [code-review, frontend, accessibility, wcag, pr-10]
dependencies: []
---

# role="menu" on profile dropdown lacks required keyboard navigation (ARIA violation)

## Problem Statement

`(app)/+layout.svelte` uses `role="menu"` on the profile dropdown and `role="menuitem"` on its children. The ARIA authoring practices specification requires that `role="menu"` widgets support arrow key navigation (`ArrowDown`, `ArrowUp`), `Escape` to close, `Home`/`End` for first/last item, and character search. The current implementation has none of this — it only closes on an outside click. Using `role="menu"` without the keyboard behavior sets a false contract with screen readers, which is worse than having no role at all.

This is a WCAG 2.1 Level AA violation (Success Criterion 4.1.2 Name, Role, Value). CLAUDE.md requires WCAG 2.1 Level AA.

## Findings

- `(app)/+layout.svelte` lines 216–244: `role="menu"` div with `role="menuitem"` children
- No `keydown` handler on the menu element
- No focus management when menu opens/closes
- Existing close behavior: `onclick` outside via `use:clickOutside` (or equivalent) only
- Pre-existing issue; file was modified in PR #10 so it is appropriate to flag now
- Identified by kieran-typescript-reviewer

## Proposed Solutions

### Option 1: Remove ARIA role (Recommended for now)

Remove `role="menu"` and `role="menuitem"` from the profile dropdown. Replace with a plain `<nav>` or `<div>` with standard link/button elements.

A dropdown nav that closes on outside click is perfectly accessible without menu roles — links are keyboard-reachable via Tab, and no false contract is set.

**Pros:** Removes the accessibility violation immediately. Simple fix.
**Cons:** Loses the semantic "menu" announcement for screen readers (but this is better than a broken menu widget).
**Effort:** Small
**Risk:** Low

### Option 2: Implement full ARIA menu keyboard pattern

Add a `keydown` handler implementing the full ARIA menu pattern: `ArrowDown`/`ArrowUp` to move focus, `Escape` to close, `Home`/`End` for boundaries.

**Pros:** Correct, complete implementation. Best screen reader experience.
**Cons:** ~40 lines of keyboard logic. More complex.
**Effort:** Medium (1–2 hours)
**Risk:** Medium — keyboard event handling has edge cases

## Recommended Action

Option 1 in the short term (remove the roles, stop the ARIA violation). Option 2 can be a follow-up enhancement.

## Technical Details

- File: `frontend/src/routes/(app)/+layout.svelte` lines 216–244

## Acceptance Criteria

- [ ] No `role="menu"` or `role="menuitem"` in app layout without the corresponding keyboard behavior
- [ ] Profile dropdown is keyboard-accessible (Tab to reach, Enter/Space to open, Tab through items, Escape to close)
- [ ] No ARIA role misuse (axe-core audit passes for the nav area)

## Work Log

- 2026-03-25: Identified by kieran-typescript-reviewer in PR #10 review
2026-03-25: Resolved.
