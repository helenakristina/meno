---
status: done
priority: p1
issue_id: "073"
tags: [code-review, frontend, accessibility, wcag, design-system, pr-10]
dependencies: []
---

# WCAG AA contrast failure: primary-600 teal text on white background (~3.1:1, needs 4.5:1)

## Problem Statement

`primary-600` (`#0d9478`) on white (`#ffffff`) achieves approximately **3.1:1** contrast ratio. WCAG 2.1 AA requires 4.5:1 for normal text. This affects navigation active links, citation links in Ask Meno, and the hardcoded hex values in the ask page style block. This PR introduced the failing color — the previous near-navy `--primary` was much darker and would have passed. CLAUDE.md states WCAG 2.1 Level AA as a requirement.

`primary-500` (`#14b892`) on white for button text is ~2.9:1, also failing.

## Findings

- `(app)/+layout.svelte` line 130: `text-primary-600` for active nav item text
- `ask/+page.svelte` line 307: `text-primary-600 hover:text-primary-800` for citation links
- `ask/+page.svelte` style block line 398: hardcoded `color: #0d9478` for `.citation-ref`
- `ask/+page.svelte` style block line 490: hardcoded `color: #0d9478` for `.message-content a`
- `primary-800` (`#115e50`) on white is ~7.0:1 — passes AAA
- `primary-700` (`#0f7663`) on white is ~4.2:1 — borderline, close to AA but slightly under
- Buttons with `bg-primary-500 text-white`: white on `#14b892` is ~2.9:1 (also fails, but buttons have other affordances; WCAG 1.4.3 focus is on text)
- Identified by security-sentinel

## Proposed Solutions

### Option 1: Use primary-800 for interactive text (Recommended)

Replace `text-primary-600` with `text-primary-800` (`#115e50`, ~7.0:1) for all text uses.
Update hardcoded hex in style block from `#0d9478` to `#115e50`.

**Pros:** Passes both AA and AAA. Safe, no ambiguity.
**Cons:** Darker teal may look more muted against white nav.
**Effort:** Small
**Risk:** Low

### Option 2: Use primary-700 for interactive text

Replace `text-primary-600` with `text-primary-700` (`#0f7663`, ~4.2:1).

**Pros:** Closer to the original design intent (medium teal, not too dark).
**Cons:** 4.2:1 is still slightly below the 4.5:1 threshold — technically still failing AA for normal text.
**Effort:** Small
**Risk:** Low — visual risk only

### Option 3: Add Inter bold weight to borderline uses

`text-primary-600` at 14px bold qualifies as "large text" under WCAG (18.67px bold or 24px regular), which only requires 3:1. Bold nav links at 14px (`font-medium`) narrowly miss this — would need `font-bold` to qualify.

**Pros:** Minimal color change.
**Cons:** Bolder nav text may not match design intent.
**Effort:** Small
**Risk:** Low

## Recommended Action

Option 1 (`primary-800`) for all text uses. Reserve `primary-500/600` for background fills (buttons, chips, progress bars) where the white-on-teal contrast question is evaluated differently.

## Technical Details

- Files: `(app)/+layout.svelte`, `ask/+page.svelte` (class + style block)
- Also audit for any other `text-primary-600` uses: `grep -r "text-primary-600" frontend/src`

## Acceptance Criteria

- [ ] No `text-primary-600` used for normal-weight body/nav text on white backgrounds
- [ ] Hardcoded `#0d9478` in `ask/+page.svelte` style block replaced with compliant value
- [ ] Chrome DevTools accessibility audit passes for primary-colored text elements
- [ ] Contrast ratio ≥ 4.5:1 for all primary-colored text at normal weight

## Work Log

- 2026-03-25: Identified by security-sentinel in PR #10 review
2026-03-25: Resolved.
