---
status: complete
priority: p2
issue_id: "122"
tags: [code-review, accessibility, frontend, about]
---

# External link opens new tab with no accessible warning (WCAG 2.4.4)

## Problem Statement

The "Meno case study" link in `about/+page.svelte` opens in a new tab (`target="_blank"`) but provides no visual or accessible indication that it leaves the site. Screen reader users navigating by links hear only "Meno case study" with no announcement of the new-tab behavior. WCAG 2.4.4 (Link Purpose) advises that links opening new windows warn users.

**File:** `frontend/src/routes/about/+page.svelte:61-66`

```svelte
<a
  href="https://helena-lucia.vercel.app/meno"
  target="_blank"
  rel="noopener noreferrer"
  class="text-primary-600 underline underline-offset-2 hover:text-primary-700"
>Meno case study</a>
```

## Findings

- **File:** `frontend/src/routes/about/+page.svelte:61-66`
- **Flagged by:** kieran-typescript-reviewer

## Proposed Solutions

### Option A: Add visually hidden `sr-only` span (recommended)

```svelte
<a
  href="https://helena-lucia.vercel.app/meno"
  target="_blank"
  rel="noopener noreferrer"
  class="text-primary-600 underline underline-offset-2 hover:text-primary-700"
>
  Meno case study
  <span class="sr-only">(opens in new tab)</span>
</a>
```

No visual change; screen readers announce "(opens in new tab)".

**Pros:** Minimal change, standard pattern, zero visual impact  
**Cons:** None  
**Effort:** Trivial  
**Risk:** None

### Option B: Add external link icon

Add a small SVG external link icon after the link text with `aria-hidden="true"`. Visually signals new tab to sighted users.

**Pros:** Helps sighted users too  
**Cons:** Requires an SVG icon, slightly more markup  
**Effort:** Small  
**Risk:** None

## Acceptance Criteria

- [ ] Screen reader announces that the link opens in a new tab
- [ ] Visual appearance unchanged (Option A) or improves (Option B)

## Work Log

- 2026-04-11: Identified by PR #22 code review (kieran-typescript-reviewer)
