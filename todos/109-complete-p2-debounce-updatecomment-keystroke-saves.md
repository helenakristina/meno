---
status: complete
priority: p2
issue_id: "109"
tags: [code-review, frontend, appointment-prep, performance, sessionstorage]
---

# Debounce `updateComment` in Step3Prioritize — fires saveToSession on every keystroke

## Problem Statement

`updateComment` in `Step3Prioritize.svelte` is called via `oninput` on the concern comment textarea. Every keystroke (insertion, deletion, paste, autocorrect) triggers:

```
oninput → updateComment → onChange?.(updated) → handleConcernsChange (parent) → state.concerns = concerns + saveToSession() → JSON.stringify(state) + sessionStorage.setItem(...)
```

This means:

1. `JSON.stringify` + `sessionStorage.setItem` on every character typed
2. Parent `state.concerns` is mutated on every character (causes Svelte to propagate through the full reactive graph)
3. Any `$derived` values computed from `state.concerns` in the future would recompute on every keystroke

The current state object serialization is small (~2-9KB) and fast (<1ms), so this is not a perceptible lag. The real concern is the per-keystroke parent state mutation — a subtle trap for future reactive dependencies built on `state.concerns`.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte` lines 71–76
  ```ts
  function updateComment(index: number, comment: string) {
    const updated = [...concerns];
    updated[index] = { ...updated[index], comment: comment || undefined };
    concerns = updated;
    onChange?.(updated); // ← fires on every keystroke
  }
  ```
- **Template:** `oninput={(e) => updateComment(i, (e.currentTarget as HTMLTextAreaElement).value)}` (line 213)
- **Contrast:** All other `onChange` calls (moveUp, moveDown, removeConcern, addConcern, handleDrop) fire on discrete user actions — exactly once per user interaction. Only `updateComment` fires on continuous input.

## Proposed Solutions

### Option A: Debounce `onChange` in updateComment (Recommended)

Update local `concerns` state immediately (for UI: character counter, textarea value), but debounce the `onChange` callback to fire 300ms after the user stops typing:

```ts
let commentDebounceTimer: ReturnType<typeof setTimeout> | null = null;

function updateComment(index: number, comment: string) {
  const updated = [...concerns];
  updated[index] = { ...updated[index], comment: comment || undefined };
  concerns = updated; // immediate local update (UI stays in sync)

  if (commentDebounceTimer) clearTimeout(commentDebounceTimer);
  commentDebounceTimer = setTimeout(() => {
    onChange?.(updated);
    commentDebounceTimer = null;
  }, 300);
}
```

The textarea and character counter update on every keystroke. Only the sessionStorage write is deferred.

- Effort: Small | Risk: Low — single timer, cleanup on component destroy if needed

### Option B: Use `onchange` instead of `oninput`

`onchange` fires on blur (when the user leaves the field), not on every keystroke. This eliminates all per-keystroke saves.

Change the template from `oninput` to `onchange`. Note: the character counter (`{(concern.comment ?? '').length}/200`) would no longer update in real-time — it would only update on blur. Acceptable if live counting is not a hard requirement.

- Effort: XS | Risk: Low — slight UX change (live counter becomes blur-triggered)

### Option C: Accept current behavior

For the current state object size and the health app's usage scale, the per-keystroke overhead is genuinely negligible. Add a comment explaining the trade-off and defer indefinitely.

- Effort: XS | Risk: None

## Acceptance Criteria (if fixing)

- [ ] Typing in a concern comment textarea does not trigger `onChange` on every character
- [ ] After the user stops typing for 300ms, `onChange` fires once and sessionStorage is updated
- [ ] The textarea value and character counter still update in real-time (no UX regression)
- [ ] On step advance (`onNext`), the most recent comment value is saved regardless of debounce state

## Work Log

- 2026-04-11: Found during code review by performance reviewer agent
