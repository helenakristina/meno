---
status: done
priority: p2
issue_id: "077"
tags: [code-review, frontend, design-system, cleanup, pr-10]
dependencies: []
---

# Dead CSS token groups in layout.css: sidebar (~24 lines), chart (~15 lines), bg-* (~5 lines)

## Problem Statement

`layout.css` contains three groups of CSS custom properties that are defined but referenced by zero components. They are shadcn scaffold boilerplate that was never cleaned up. Together they account for ~44 lines (~24% of the file). Having unused token groups creates confusion about what is part of the active design system vs. legacy scaffolding.

## Findings

**Sidebar tokens (~24 lines):**
- `:root` lines 34–41: `--sidebar`, `--sidebar-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring`
- `.dark` lines 68–75: same 8 vars
- `@theme inline` lines 106–113: 8 aliases
- Zero references in any `.svelte` file — the mobile menu is a `<div>`, not a semantic sidebar component
- Identified by code-simplicity-reviewer

**Chart tokens (~15 lines):**
- `:root` lines 29–33: `--chart-1` through `--chart-5`
- `.dark` lines 63–67: same 5 vars
- `@theme inline` lines 101–105: 5 aliases
- Zero references — the dashboard frequency chart uses `bg-primary-500` with inline `style="width: X%"`, not chart tokens
- Identified by code-simplicity-reviewer

**Background semantic group (~5 lines):**
- `@theme inline` lines 165–169: `--color-bg-page`, `--color-bg-card`, `--color-bg-subtle`, `--color-bg-overlay`
- Zero references — components use `bg-white`, `bg-neutral-50`, `bg-black/30` directly
- `--color-bg-subtle` (`#fafaf9`) is identical to `--color-neutral-50` (`#fafaf9`) — duplicate value
- Identified by code-simplicity-reviewer

## Proposed Solutions

### Option 1: Delete all three groups (Recommended)

Remove all three token groups from `:root`, `.dark`, and `@theme inline`. Total: ~44 lines removed.

**Pros:** Smaller file, clearer token surface, no YAGNI violations
**Cons:** If a chart library is added later, chart tokens would need to be re-added (but that is speculative)
**Effort:** Small (30 min, including verification)
**Risk:** Very low — verify with `grep` that no component references these before deleting

**Verification command:**
```bash
grep -r "sidebar\|chart-[1-5]\|bg-bg-" frontend/src --include="*.svelte" --include="*.ts"
```

## Recommended Action

Option 1. Remove all three groups. Add them back if/when a chart library or sidebar component is actually added.

## Technical Details

- File: `frontend/src/routes/layout.css`
- Sidebar: `:root` 34–41, `.dark` 68–75, `@theme` 106–113
- Chart: `:root` 29–33, `.dark` 63–67, `@theme` 101–105
- Bg-*: `@theme` 165–169

## Acceptance Criteria

- [ ] No `--sidebar-*` variables in layout.css
- [ ] No `--chart-*` variables in layout.css
- [ ] No `--color-bg-page/card/subtle/overlay` in layout.css
- [ ] No components broken (grep confirms zero pre-existing references)
- [ ] layout.css is ≤ 145 lines (down from ~184)

## Work Log

- 2026-03-25: Identified by code-simplicity-reviewer in PR #10 review
2026-03-25: Resolved.
