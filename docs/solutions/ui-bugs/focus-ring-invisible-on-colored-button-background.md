---
title: Focus ring invisible on colored button background (WCAG 2.4.7)
category: ui-bugs
date: 2026-04-12
tags: [accessibility, wcag, tailwind, focus-ring, svelte, frontend]
components: [contact, public-pages]
severity: p1
---

# Focus ring invisible on colored button background

## Problem

A submit button with `bg-primary-500` (teal) had a focus ring applied via `focus-visible:ring-2 focus-visible:ring-primary-400`. The ring was virtually invisible because `primary-400` is only one step lighter than `primary-500` — the ring blends directly into the button surface with no contrast gap. This is a WCAG 2.1 AA failure under SC 2.4.7 (Focus Visible): keyboard users receive no meaningful visual focus indication.

**Symptom**: Tab to the button and see no visible focus indicator.

**File**: `frontend/src/routes/contact/+page.svelte`

## Root Cause

Tailwind's `focus-visible:ring-*` renders the ring flush against the element border without any gap. When the ring color is the same hue as the background (even a different shade), there is zero contrast. A `ring-offset` is required to create a white gap between the element and the ring, making the ring visible regardless of the button's background color.

## Solution

Use a white ring with an offset that matches the button background color:

```svelte
<!-- Before (invisible) -->
class="... focus-visible:ring-2 focus-visible:ring-primary-400"

<!-- After (clearly visible) -->
class="... focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-500"
```

**How it works:**

- `ring-white` — the ring itself is white, maximally contrasting with anything
- `ring-offset-2` — creates a 2px gap (transparent by default) between the element edge and the ring
- `ring-offset-{bg-color}` — fills the gap with the button's background color so it looks like an inset ring

This creates the visual appearance: `[teal button] [teal gap] [white ring]` — immediately readable against any page background.

## Prevention

For any button or interactive element with a colored background:

1. **Never use a same-hue ring color** — `primary-400` on `primary-500` fails.
2. **Always add `ring-offset-2`** when the element has a non-white background.
3. **Use `ring-white`** for primary/colored buttons. Use `ring-primary-500` for white/outline buttons.

### Quick reference by button type

| Button type                  | Ring pattern                                      |
| ---------------------------- | ------------------------------------------------- |
| Primary (colored bg)         | `ring-white ring-offset-2 ring-offset-{bg-color}` |
| Secondary (white/outline bg) | `ring-primary-500 ring-offset-2`                  |
| Ghost/link                   | `ring-primary-500` (no offset needed)             |

### Linting tip

Search for `focus-visible:ring-2` without a corresponding `ring-offset` on elements with `bg-primary-*` or `bg-coral-*`:

```bash
grep -rn "bg-primary.*focus-visible:ring-2\|focus-visible:ring-2.*bg-primary" frontend/src/
```

## References

- [WCAG 2.1 SC 2.4.7 Focus Visible](https://www.w3.org/WAI/WCAG21/Understanding/focus-visible.html)
- [Tailwind ring-offset docs](https://tailwindcss.com/docs/ring-offset-width)
- Fixed in: `frontend/src/routes/contact/+page.svelte` (todo #119, PR #22 review)
