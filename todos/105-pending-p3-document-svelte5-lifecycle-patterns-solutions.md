---
status: pending
priority: p3
issue_id: "105"
tags: [code-review, documentation, svelte5, patterns, learnings]
---

# Document three new Svelte 5 lifecycle patterns in docs/solutions/

## Problem Statement

The appointment prep state persistence fix (`13f72a6`) revealed three non-obvious Svelte 5 patterns that have no existing documentation in `docs/solutions/`. These are gotchas that the compiler does not warn about. Without documentation, future developers are likely to repeat the same mistakes.

The learnings researcher confirmed: no existing solution documents cover these topics. The `$derived` thunk bug documented in `docs/solutions/ui-bugs/svelte5-derived-thunk-and-bits-ui-calendar-key-collision.md` is a cousin of the first pattern but doesn't cover the `$effect`/`onMount` race specifically.

## Findings

**Pattern 1: `$effect` fires before `onMount` — race with sessionStorage restore**

In Svelte 5, `$effect` runs synchronously during component initialization (after the first render, before `onMount`). Any `$effect` that writes to sessionStorage or shared state will overwrite values that `onMount` hasn't had a chance to load yet. Fix: initialize state from sessionStorage inside `onMount`, and use explicit saves (not `$effect`) for writes.

**Pattern 2: sessionStorage sole-writer pattern in multi-step flows**

When a parent component owns sessionStorage and child step components receive data via props, the parent must be the sole writer. Child components reading and re-persisting their own prop values create a race with parent initialization. The child's write should only happen via callbacks that the parent controls.

**Pattern 3: LLM API call guard in `onMount`**

Step components that call an LLM API in `onMount` must check whether the data they need already exists (passed as a prop from parent's restored state) before making the call. Pattern:
```typescript
onMount(() => {
  if (existingData !== null) return;  // skip — already have it
  callLLM();
});
```

## Proposed Solutions

### Option A: Create a single consolidated pattern file
Create `docs/solutions/patterns/svelte5-lifecycle-patterns.md` covering all three patterns with code examples and the specific bug they prevented.
- Effort: Small | Risk: None

### Option B: Add to existing Svelte 5 bug document
Extend `docs/solutions/ui-bugs/svelte5-derived-thunk-and-bits-ui-calendar-key-collision.md` with a "Related Patterns" section.
- Effort: Tiny | Risk: None — but loses discoverability

## Acceptance Criteria
- [ ] At least one new file in `docs/solutions/` covers the `$effect`/`onMount` race pattern
- [ ] The LLM API call guard pattern is documented
- [ ] The sessionStorage sole-writer pattern is documented
- [ ] Files are searchable by keyword (effect, onMount, sessionStorage, LLM guard)

## Work Log
- 2026-04-11: Found during code review of commit 13f72a6. Learnings researcher confirmed no existing docs cover these patterns.
