---
title: "Debounce closure captures stale state snapshot — concurrent mutations silently discarded"
category: runtime-errors
date: 2026-04-11
tags:
  [
    svelte5,
    debounce,
    closure,
    state,
    appointment-prep,
    sessionstorage,
    correctness,
  ]
components: [frontend, appointment-prep]
severity: p1
---

# Debounce Closure Captures Stale State Snapshot

## Problem Symptom

User types a comment on a concern, then reorders concerns within 300ms (drag, up/down button). The reorder is visible immediately in the UI — but after 300ms, the sessionStorage write fires and silently rolls back the reorder. On the next page reload, the pre-drag order is restored. No error, no warning.

## Root Cause

The debounce closure captured the local `updated` array (a snapshot from when the keystroke fired), not the live reactive state:

```ts
function updateComment(index: number, comment: string) {
  const updated = [...concerns];
  updated[index] = { ...updated[index], comment: comment || undefined };
  concerns = updated; // ✓ immediate local update — UI is correct

  if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
  commentDebounceTimer = setTimeout(() => {
    onChange?.(updated); // ✗ stale snapshot from THIS keystroke
    commentDebounceTimer = null;
  }, 300);
}
```

When the user types character N, `updated` is a snapshot of concerns at that moment. The timer is set with that snapshot closed over. If the user drags concern #2 to position #4 within 300ms, `concerns` reflects the drag — but the pending timer still holds the pre-drag `updated`. When the timer fires, `onChange(updated)` writes the old order to sessionStorage, overwriting the drag.

The bug is compiler-silent: `updated` is a valid array, the types are correct, and tests that only check "was onChange called with the right value at the right time" will pass without catching the concurrent-mutation scenario.

## Solution

Read the reactive state variable inside the timeout callback instead of closing over the snapshot:

```ts
function updateComment(index: number, comment: string) {
  const updated = [...concerns];
  updated[index] = { ...updated[index], comment: comment || undefined };
  concerns = updated; // immediate local update for UI

  if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
  commentDebounceTimer = setTimeout(() => {
    onChange?.(concerns); // ✓ read current state at fire time
    commentDebounceTimer = null;
  }, 300);
}
```

In Svelte 5, `$state` variables are synchronously readable inside `setTimeout` callbacks — `concerns` at fire time reflects all mutations that happened during the debounce window (comments, reorders, removes, adds).

Also add `onDestroy` cleanup to prevent the timer firing against a destroyed component:

```ts
import { onDestroy } from "svelte";

onDestroy(() => {
  if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
});
```

## Prevention

**Rule:** In debounced functions that write shared/persisted state, never close over a local snapshot. Always read the source-of-truth variable at fire time.

```ts
// ✗ Anti-pattern — snapshot captured at schedule time
const snapshot = [...items];
setTimeout(() => persist(snapshot), 300);

// ✓ Correct — reads current state at fire time
setTimeout(() => persist(items), 300);
```

This applies to any debounce over Svelte `$state`, React `useRef`-backed state, or any mutable variable that can be updated between schedule and fire.

## Related

- `docs/solutions/patterns/svelte5-lifecycle-patterns.md` — related Svelte 5 timing gotchas
- Commit: `a014c3a` (todo 112 resolution)
