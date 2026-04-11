---
status: pending
priority: p1
issue_id: "112"
tags: [code-review, frontend, appointment-prep, svelte5, correctness, bug]
---

# Debounce closure captures stale `updated` snapshot — concurrent changes silently discarded

## Problem Statement

`updateComment` in `Step3Prioritize.svelte` captures the `updated` array (a snapshot of concerns at keystroke time) in the debounce closure. If the user types in a comment textarea and then reorders or removes a concern within 300ms, the debounced `onChange` fires with the stale `updated` snapshot, overwriting the reorder with the old concern order.

This is a silent data loss bug: the user sees the reorder happen visually (because `concerns = updated` fires immediately), but the sessionStorage write that follows 300ms later rolls it back.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte` lines 71-83
- **Current code:**
  ```ts
  function updateComment(index: number, comment: string) {
      const updated = [...concerns];
      updated[index] = { ...updated[index], comment: comment || undefined };
      concerns = updated; // immediate local update ✓

      if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
      commentDebounceTimer = setTimeout(() => {
          onChange?.(updated);  // ← stale snapshot from this keystroke
          commentDebounceTimer = null;
      }, 300);
  }
  ```
- **Scenario:** User types "my comment", then immediately drags concern #1 to position #3. Debounce fires with the pre-drag `updated` array, reverting the drag in sessionStorage (UI shows dragged order, but next page reload restores pre-drag order).

## Proposed Solution

Read `concerns` (current state) inside the timeout callback instead of closing over the snapshot:

```ts
commentDebounceTimer = setTimeout(() => {
    onChange?.(concerns);  // read current Svelte state at fire time
    commentDebounceTimer = null;
}, 300);
```

Svelte 5 `$state` values are synchronously readable. `concerns` inside the timeout will reflect all mutations that happened during the 300ms window.

- Effort: XS | Risk: None

## Acceptance Criteria
- [ ] Reordering concerns within 300ms of typing a comment preserves the reorder in sessionStorage
- [ ] Comment text typed in the 300ms window is still correctly saved
- [ ] No regression in debounce behavior (sessionStorage write still deferred)

## Work Log
- 2026-04-11: Found during performance review of commit e690800
