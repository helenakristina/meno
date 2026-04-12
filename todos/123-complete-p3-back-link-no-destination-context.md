---
status: complete
priority: p3
issue_id: "123"
tags: [code-review, accessibility, frontend]
---

# "Back" link lacks destination context for screen reader users

## Problem Statement

All three public pages have a back arrow link that reads "← Back" with no destination context. Screen reader users navigating by links list hear only "Back" and cannot determine where the link leads without following it. WCAG 2.4.6 (Headings and Labels) advisory guidance recommends descriptive link text.

**Files:**

- `frontend/src/routes/about/+page.svelte:18-23`
- `frontend/src/routes/privacy/+page.svelte:18-23`
- `frontend/src/routes/contact/+page.svelte:18-23`

This will be automatically fixed in all three places once the shared shell component is extracted (todo #120).

## Proposed Solutions

### Option A: Add `sr-only` span with destination

```svelte
<a href="/" class="text-sm font-medium text-neutral-500 transition-colors hover:text-neutral-700">
  &larr; Back <span class="sr-only">to home</span>
</a>
```

**Effort:** Trivial (but fix in the shell component, not three separate files)

### Option B: Update visible text to "Back to home"

More explicit for all users, not just AT users.

**Effort:** Trivial

## Acceptance Criteria

- [ ] The back link's accessible name conveys its destination
- [ ] Fix applied in the shared shell (not triplicated)

## Work Log

- 2026-04-11: Identified by PR #22 code review (architecture-strategist, typescript-reviewer)
