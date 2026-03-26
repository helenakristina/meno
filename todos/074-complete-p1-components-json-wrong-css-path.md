---
status: done
priority: p1
issue_id: "074"
tags: [code-review, frontend, shadcn, tooling, pr-10]
dependencies: []
---

# components.json has wrong CSS path — future shadcn additions will miss design tokens

## Problem Statement

`frontend/components.json` line 4 sets `"css": "src/app.css"`. No `src/app.css` file exists — the actual CSS entry point is `src/routes/layout.css`. The shadcn-svelte CLI uses this path to inject its CSS variable definitions when running `npx shadcn-svelte add <component>`. With the wrong path, any newly added shadcn component will generate with CSS references that don't resolve to the Meno token definitions, silently breaking the design token system for new components.

Additionally, `"baseColor": "slate"` on line 6 means the CLI generates new components pre-seeded with slate-based (cool gray) defaults — the exact palette the design system overhaul replaced.

## Findings

- `frontend/components.json` line 4: `"css": "src/app.css"` — file does not exist
- `frontend/components.json` line 6: `"baseColor": "slate"` — generates cool-gray defaults
- The actual CSS entry point is `frontend/src/routes/layout.css`
- Running `npx shadcn-svelte add button` (or any component) will generate with incorrect CSS path and slate color defaults
- Identified by architecture-strategist

## Proposed Solutions

### Option 1: Fix both issues (Recommended)

```json
{
  "css": "src/routes/layout.css",
  "baseColor": "stone"
}
```

`stone` is the closest Tailwind palette to the warm neutral scale Meno uses.

**Pros:** Future `shadcn-svelte add` commands will point to the correct CSS and generate warm-toned defaults.
**Effort:** Tiny (2-line change)
**Risk:** Zero

## Recommended Action

Option 1. Fix before merge.

## Technical Details

- File: `frontend/components.json`

## Acceptance Criteria

- [ ] `"css"` points to `"src/routes/layout.css"`
- [ ] `"baseColor"` is `"stone"` or `"neutral"` (not `"slate"`)
- [ ] Running `npx shadcn-svelte add` does not error on CSS path

## Work Log

- 2026-03-25: Identified by architecture-strategist in PR #10 review
2026-03-25: Resolved.
