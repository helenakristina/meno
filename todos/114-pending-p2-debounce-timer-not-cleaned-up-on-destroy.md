---
status: pending
priority: p2
issue_id: "114"
tags: [code-review, frontend, appointment-prep, svelte5, memory-leak, cleanup]
---

# `commentDebounceTimer` not cleaned up on component destroy

## Problem Statement

`commentDebounceTimer` in `Step3Prioritize.svelte` is declared at component scope but never cancelled in `onDestroy`. If the user types in a comment textarea and then navigates to the next step within 300ms, the timer fires against a destroyed component and calls `onChange?.(concerns)` — which writes stale concern data to sessionStorage in the parent after the step has already advanced.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte` line ~71
- **Current:** No `onDestroy` cleanup for `commentDebounceTimer`
- **Impact:** Stale sessionStorage write after step advance; potential for subtle state corruption on back-navigation

## Proposed Solution

Add `onDestroy` to cancel the timer:

```ts
import { onDestroy } from 'svelte';

onDestroy(() => {
    if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
});
```

- Effort: XS | Risk: None

## Acceptance Criteria
- [ ] Navigating to the next step while a comment debounce is pending does not trigger a stale sessionStorage write
- [ ] No `onDestroy` import error

## Work Log
- 2026-04-11: Found during TypeScript review of commit e690800
