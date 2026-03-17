---
status: pending
priority: p1
issue_id: "029"
tags: [code-review, svelte5, frontend, anti-pattern]
dependencies: []
---

# `$effect` used for one-time session init in `+layout.svelte` — should be `onMount`

## Problem Statement

`+layout.svelte` uses `$effect(() => { supabase.auth.getSession().then(() => { loading = false; }); })` for session initialization. This is the project's documented anti-pattern: `$effect` re-runs whenever reactive dependencies change and should NOT be used for one-time initialization. The convention is explicit: use `onMount` for initial data loading.

The adjacent settings fetch already correctly uses `onMount` — making this inconsistency visible.

## Findings

- **File**: `frontend/src/routes/(app)/+layout.svelte:19-23`
- No reactive dependencies inside the effect, so it only fires once — but the intent is one-time init which belongs in `onMount`
- Also: `$effect` for auth redirect (lines 26-30) may fire spuriously if `authState` flickers during session refresh

## Proposed Solution

```typescript
onMount(async () => {
    await supabase.auth.getSession();
    loading = false;
});
```

For auth redirect, consider checking inside the existing `onMount` rather than a separate `$effect`.

## Acceptance Criteria
- [ ] Session init uses `onMount`, not `$effect`
- [ ] Auth redirect guard is stable (won't fire on transient auth state changes)
