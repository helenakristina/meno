---
status: done
priority: p2
issue_id: "076"
tags: [code-review, frontend, design-system, naming, pr-10]
dependencies: []
---

# accent-* naming collision: shadcn neutral hover vs Meno coral/orange — rename to coral-*

## Problem Statement

The name `accent` is used for two completely different color scales:
- `bg-accent` (shadcn semantic) → `--accent` → `oklch(0.968 0.007 247.896)` — a muted blue-gray, used for ghost button hovers and menu hover backgrounds in shadcn components
- `bg-accent-100` through `bg-accent-900` (Meno custom) → coral/orange scale, used for period flow levels and provider call status badges

A developer reading `hover:bg-accent` in `button.svelte` and `bg-accent-400` in `PeriodCalendar.svelte` will reasonably assume they are related. They are in completely different hue families. This will cause confusion and incorrect color usage when authoring new components.

Confirmed independently by 3 review agents: kieran-typescript-reviewer, performance-oracle, architecture-strategist.

## Findings

- `layout.css` line 95: `--color-accent: var(--accent)` (shadcn, blue-gray)
- `layout.css` lines 140–149: `--color-accent-50` through `--color-accent-900` (Meno coral/orange)
- `PeriodCalendar.svelte` lines 63–67, 124, 131, 134, 159–171: all use `accent-*` (coral)
- `PeriodLogModal.svelte` lines 35–38, 187, 222, 229, 244, 260, 263, 282, 298: all use `accent-*` (coral)
- `CallingScriptModal.svelte` line 121: `to_call: 'text-accent-700 border-accent-200 bg-accent-50'`
- `providers/+page.svelte` line 95: `bg-accent-100 text-accent-800` for `to_call` badge
- `button.svelte` lines 53, 55: `hover:bg-accent hover:text-accent-foreground` (shadcn neutral)

## Proposed Solutions

### Option 1: Rename Meno coral scale to coral-* (Recommended)

In `layout.css`, rename `--color-accent-50` through `--color-accent-900` to `--color-coral-50` through `--color-coral-900`.

Update all usages (~35 class references across 4 files):
- `PeriodCalendar.svelte`: `accent-*` → `coral-*`
- `PeriodLogModal.svelte`: `accent-*` → `coral-*`
- `CallingScriptModal.svelte`: `accent-*` → `coral-*`
- `providers/+page.svelte`: `accent-*` → `coral-*`

The shadcn `bg-accent` (no suffix) remains untouched — it maps to the blue-gray neutral.

**Pros:** `bg-accent` = shadcn neutral (unambiguous), `bg-coral-400` = period orange (unambiguous)
**Cons:** Need to update 4 files; design skill document also needs updating
**Effort:** Medium (1–2 hours including design skill doc update)
**Risk:** Low — pure rename, zero visual change

### Option 2: Rename to flow-* (period-specific)

`--color-flow-50` through `--color-flow-900`. More specific to the primary use case.

**Pros:** Self-documenting for period tracking context
**Cons:** Also used in provider call badges (not period-related) — less accurate for that use
**Effort:** Same as Option 1

## Recommended Action

Option 1 (`coral-*`). "Coral" is palette-level naming; "flow" is feature-specific. Coral aligns better with how design systems name hue families.

Also update `.claude/skills/frontend-design/SKILL.md` to rename the accent scale to coral.

## Technical Details

- Layout.css lines 139–149 (token definitions)
- 4 component files (~35 class references total)
- `.claude/skills/frontend-design/SKILL.md` (design skill doc)

## Acceptance Criteria

- [ ] `--color-coral-*` defined in layout.css (replacing `--color-accent-50` through `--color-accent-900`)
- [ ] No `bg-accent-{n}` or `text-accent-{n}` in PeriodCalendar, PeriodLogModal, CallingScriptModal, or providers page
- [ ] `bg-accent` (no suffix) still works for shadcn ghost button hover
- [ ] Frontend design skill updated to use `coral-*` name
- [ ] `grep "accent-[0-9]" frontend/src` returns no results

## Work Log

- 2026-03-25: Identified by kieran-typescript-reviewer, performance-oracle, architecture-strategist in PR #10 review
2026-03-25: Resolved.
