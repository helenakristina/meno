---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, frontend, accessibility, wcag]
dependencies: []
---

# Fix `role="dialog"` placement and add focus trap in PeriodLogModal

## Problem Statement

`PeriodLogModal.svelte` places `role="dialog"` on the backdrop overlay `<div>` instead of the inner panel element. This breaks screen reader semantics — the dialog role should be on the panel that contains the dialog content, not on the full-screen backdrop. Additionally, there is no focus trap: focus can escape the modal via Tab, violating WCAG 2.1 AA (which the project requires).

## Findings

- `role="dialog"` is on the outer backdrop div, not the inner panel div (TypeScript reviewer)
- No `aria-modal="true"` on the panel element
- No focus trap implementation — Tab key can move focus behind the modal
- No initial focus management (should focus first interactive element or the dialog title on open)
- Project standard: WCAG 2.1 Level AA, all interactive elements ≥ 44×44px

## Proposed Solutions

### Option 1: Move role + add focus trap manually

**Approach:**
1. Move `role="dialog"` to the inner panel div
2. Add `aria-modal="true"` and `aria-labelledby="period-log-title"` to the panel
3. Add `id="period-log-title"` to the `<h2>` inside the modal
4. Implement focus trap with a `$effect` that captures Tab/Shift+Tab keydown events

**Pros:** Full control, no new dependencies

**Cons:** Focus trap logic is ~20 lines of boilerplate

**Effort:** 1 hour

**Risk:** Low

---

### Option 2: Use bits-ui Dialog primitive

**Approach:** Replace the custom modal with `Dialog.Root` / `Dialog.Content` from bits-ui (already installed as a dependency). bits-ui Dialog handles focus trap, ARIA, and backdrop automatically.

**Pros:** Correct accessibility out of the box, matches how Calendar is implemented in this codebase, less bespoke code

**Cons:** Requires restructuring the modal component around bits-ui slots

**Effort:** 2 hours

**Risk:** Low-Medium (structural change)

## Recommended Action

Option 2 is preferred since bits-ui is already installed and used for the Calendar component. Move `role="dialog"` to panel, add `aria-modal="true"`, and use bits-ui `Dialog.Content` for the focus trap. If bits-ui refactor is too large in scope, Option 1 is acceptable as a quick fix.

## Technical Details

**Affected files:**
- `frontend/src/lib/components/period/PeriodLogModal.svelte` — backdrop and panel div structure

## Acceptance Criteria

- [ ] `role="dialog"` is on the inner panel element, not the backdrop
- [ ] `aria-modal="true"` is set on the dialog panel
- [ ] Dialog has `aria-labelledby` pointing to its heading
- [ ] Focus is trapped inside the modal when open (Tab does not escape)
- [ ] Focus moves to first interactive element on open
- [ ] Escape key closes the modal

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified ARIA role misplacement
- Confirmed missing focus trap
- Assessed bits-ui Dialog as simplest fix path
