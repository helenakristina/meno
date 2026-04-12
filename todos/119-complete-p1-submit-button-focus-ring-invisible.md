---
status: complete
priority: p1
issue_id: "119"
tags: [code-review, accessibility, frontend, contact]
---

# Submit button focus ring invisible on teal background (WCAG 2.4.7 failure)

## Problem Statement

The contact form submit button has `focus-visible:ring-2 focus-visible:ring-primary-400` but no `focus-visible:ring-offset-2`. Without a ring offset, the teal focus ring renders directly on top of the button's `bg-primary-500` background — the ring is nearly invisible because both the ring and the button surface are the same hue.

This is a WCAG 2.1 AA failure under Success Criterion 2.4.7 (Focus Visible): keyboard users navigating to the submit button receive no meaningful visual focus indication.

**File:** `frontend/src/routes/contact/+page.svelte:83`

```svelte
class="rounded-md bg-primary-500 px-5 py-2.5 text-sm font-semibold text-white
  transition-colors hover:bg-primary-600 focus:outline-none
  focus-visible:ring-2 focus-visible:ring-primary-400"
```

The ring color `primary-400` is only slightly lighter than `primary-500` — not sufficient contrast against the button background.

## Findings

- **File:** `frontend/src/routes/contact/+page.svelte:83`
- **Flagged by:** kieran-typescript-reviewer

## Proposed Solutions

### Option A: Add `ring-offset-2` and switch ring color to white (recommended)

```svelte
class="... focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-500"
```

White ring with a teal offset creates maximum contrast. This is the standard pattern for buttons with colored backgrounds.

**Pros:** High contrast, standard pattern, one-line change  
**Cons:** None  
**Effort:** Small  
**Risk:** None

### Option B: Add `ring-offset-2` with neutral ring

```svelte
class="... focus-visible:ring-2 focus-visible:ring-neutral-800 focus-visible:ring-offset-2"
```

Dark ring with white offset gap. Also accessible.

**Pros:** Consistent with other focus rings in the app  
**Cons:** Less visually distinctive on teal  
**Effort:** Small  
**Risk:** None

## Acceptance Criteria

- [ ] Submit button focus ring is clearly visible against the `bg-primary-500` background when focused via keyboard
- [ ] Ring passes WCAG 2.4.7 (Focus Visible) at Level AA

## Work Log

- 2026-04-11: Identified by PR #22 code review (kieran-typescript-reviewer)
