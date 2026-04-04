---
status: pending
priority: p1
issue_id: "086"
tags: [code-review, frontend, svelte5, bug]
dependencies: []
---

# `$effect` used for initial data load — must be `onMount`

## Problem Statement

Three places use `$effect` where `onMount` is required. The project's own rule (MEMORY.md) is explicit: "Use `onMount` for initial data loading (runs once on mount). Use `$effect` only when data should re-fetch based on reactive dependency changes."

The sessionStorage restore effect also has a reactive cycle: `state = parsed` inside an effect that tracks `state` will re-trigger the effect.

## Findings

**File 1**: `frontend/src/routes/(app)/appointment-prep/Step2Narrative.svelte`, line 18

```ts
$effect(() => {
  loadNarrative();
}); // no reactive deps — should be onMount
```

**File 2**: `frontend/src/routes/(app)/appointment-prep/Step4Scenarios.svelte`, line 18

```ts
$effect(() => {
  loadScenarios();
}); // no reactive deps — should be onMount
```

**File 3**: `frontend/src/routes/(app)/appointment-prep/+page.svelte`, lines 46–58

```ts
$effect(() => {
  const saved = sessionStorage.getItem("appointmentPrepState");
  if (saved) {
    state = parsed; // mutates reactive state inside effect → reactive cycle
  }
});
```

Setting `state` inside an effect that implicitly tracks `state` triggers re-execution. The save effect on line 61 then fires again, creating a feedback loop in Svelte's runtime.

## Proposed Solution

```ts
// Step2Narrative.svelte, Step4Scenarios.svelte
import { onMount } from "svelte";
onMount(() => {
  loadNarrative();
}); // or loadScenarios()

// +page.svelte — sessionStorage restore
onMount(() => {
  const saved = sessionStorage.getItem("appointmentPrepState");
  if (saved) {
    try {
      state = JSON.parse(saved);
      savedStateExists = true;
    } catch {
      savedStateExists = false;
    }
  }
});
// keep the save $effect as-is — that's a genuine reactive side effect
```

## Acceptance Criteria

- [ ] `Step2Narrative.svelte`: `$effect` replaced with `onMount` for `loadNarrative()`
- [ ] `Step4Scenarios.svelte`: `$effect` replaced with `onMount` for `loadScenarios()`
- [ ] `+page.svelte`: sessionStorage restore moved to `onMount`
- [ ] Save effect on line 61 remains as `$effect` (correct)
- [ ] All 92 frontend tests still pass
