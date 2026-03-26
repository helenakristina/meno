---
status: ready
priority: p3
issue_id: "081"
tags: [code-review, frontend, design-system, typography, pr-10]
dependencies: []
---

# Font stack tokens (Inter, JetBrains Mono) defined but neither font is loaded

## Problem Statement

`layout.css` defines `--font-sans: 'Inter', ...` and `--font-mono: 'JetBrains Mono', 'Fira Code', monospace` but neither Inter nor JetBrains Mono is loaded anywhere via `<link>`, `@font-face`, or Google Fonts import. The tokens are promises the app doesn't keep — users see the system fallback font instead.

## Findings

- `layout.css` lines 172–173: `--font-sans` and `--font-mono` definitions with named fonts
- No `@font-face` or `<link rel="preload" as="font">` in `+layout.svelte` or `layout.css`
- No Google Fonts import in the CSS entry point
- `font-mono` is used in one place: `appointment-prep/history/+page.svelte` (a `<code>` block) — falls back to browser default monospace
- Identified by code-simplicity-reviewer

## Proposed Solutions

### Option 1: Load Inter via Google Fonts (Recommended)

Add to the `<head>` in `frontend/src/routes/+layout.svelte`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

Inter is what the design skill specifies and is already used by many modern health apps.

**Pros:** Actually loads the designed font
**Cons:** Network request; adds ~50KB. Can use `display=swap` to avoid blocking render.
**Effort:** Small
**Risk:** Low (font-swap prevents FOIT)

### Option 2: Use system font stack only (Remove the token overrides)

Remove the `--font-sans` and `--font-mono` overrides from `layout.css`. Let Tailwind's default system font stack (`ui-sans-serif, system-ui, ...`) apply.

**Pros:** No network request, no FOIT, slightly faster load
**Cons:** Loses Inter — app won't match design intent
**Effort:** Tiny
**Risk:** Zero

## Recommended Action

Option 1 if the design intent for Inter is firm. Option 2 if fonts aren't a priority for the current phase (V1/V2).

## Technical Details

- `frontend/src/routes/layout.css` lines 172–173
- `frontend/src/routes/+layout.svelte` (head section)

## Acceptance Criteria

- [ ] Either: Inter is loaded and renders in the browser
- [ ] Or: Font token overrides are removed and system fonts are used intentionally
- [ ] No "aspirational" font token that isn't loaded

## Work Log

- 2026-03-25: Identified by code-simplicity-reviewer in PR #10 review
