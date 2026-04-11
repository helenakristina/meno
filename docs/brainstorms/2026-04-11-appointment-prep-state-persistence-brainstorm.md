# Appointment Prep State Persistence — Brainstorm

**Date:** 2026-04-11
**Status:** Ready for planning

---

## What We're Building

A bug fix for the appointment prep multi-step flow. Currently, navigating backward in the flow or refreshing the page wipes all previously generated content and user edits. We're fixing two root-cause bugs so that state survives both in-page back navigation and full page refreshes.

---

## Root Causes

### Bug 1 — `$effect` races with `onMount`

In Svelte 5, `$effect` runs after initial render, _before_ `onMount`. The current code uses `$effect` to persist state to sessionStorage. The sequence on page load is:

1. Component renders with initial empty state `{appointmentId: null, ...}`
2. `$effect` fires → saves **empty state** to sessionStorage (overwrites any previously saved data)
3. `onMount` fires → reads sessionStorage → finds the empty state it just clobbered

This is why page refresh loses all state.

### Bug 2 — Step components don't receive or skip on existing data

`Step2Narrative.svelte` (and likely other step components) always call the API in `onMount`, regardless of whether the parent already has the data. The parent passes `appointmentId` but not the existing generated content. So even if Bug 1 were fixed, navigating back and then forward would re-trigger LLM generation.

---

## What We're Building (Design)

### Fix for Bug 1 — Remove `$effect`, use explicit saves

Remove the reactive `$effect(() => sessionStorage.setItem(...))` entirely.

Instead, call a `saveToSession()` helper explicitly inside each step handler and in `goBack()`:

```typescript
function saveToSession() {
  sessionStorage.setItem("appointmentPrepState", JSON.stringify(state));
}

async function handleStep1(context) {
  // ... API call ...
  state.currentStep = 2;
  saveToSession(); // explicit
}

function goBack() {
  state.currentStep--;
  saveToSession(); // explicit
}
```

The `onMount` load stays as-is — it already works correctly.

### Fix for Bug 2 — Pass existing data as props to step components

Each step component should receive its previously generated data as an optional prop. On `onMount`, check if data already exists before calling the API:

```svelte
<!-- Step2Narrative.svelte -->
let {
  appointmentId,
  existingNarrative = null,  // NEW
  onNext
} = $props();

let narrative = $state(existingNarrative ?? '');

onMount(() => {
  if (existingNarrative) return;  // skip if we already have it
  loadNarrative();
});
```

Parent passes the existing value:

```svelte
<Step2Narrative
  appointmentId={state.appointmentId}
  existingNarrative={state.narrative}
  onNext={handleStep2}
/>
```

Apply the same pattern to all steps that make API/LLM calls on mount.

---

## Key Decisions

| Decision                            | Choice                      | Rationale                                                                       |
| ----------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| Remove `$effect` for sessionStorage | Yes                         | `$effect` runs before `onMount` in Svelte 5, causing the save to race with load |
| Explicit saves vs reactive          | Explicit                    | Easier to trace, no reactivity footgun, clear save points                       |
| Pass existing data as props         | Yes                         | Step components need to know if data already exists to skip regeneration        |
| SessionStorage vs module store      | Keep sessionStorage         | Survives page refresh; module store would be lost on SvelteKit navigation       |
| Database-backed state               | Out of scope (V2 if needed) | Overkill for this bug fix; appointments already saved by ID if we need it later |

---

## Steps Affected

All steps that call API/LLM on mount need the guard:

- Step 2 (Narrative) — POST generates LLM narrative
- Step 3 Qualitative — check if it makes API calls on mount
- Step 4 (Scenarios) — check if it makes API calls on mount

Steps with only local state (Step 3 Prioritize — concern reordering) already work correctly via parent state.

---

## Resolved Questions

- **Should we use `$effect` for sessionStorage?** No — explicit saves chosen. `$effect` creates a timing bug with `onMount` in Svelte 5.
- **Which persistence approach?** Keep sessionStorage (fix the bug), not a full rewrite to a module store or server-backed state.

---

## Out of Scope

- Cross-device or cross-session persistence (requires DB-backed state)
- `startOver()` behavior — already works correctly (clears sessionStorage explicitly)

---

## Success Criteria

- Page refresh at any step restores the user to where they were, with all generated content intact
- Pressing Back at any step shows the previous step's content (not blank or regenerated)
- No unnecessary LLM API calls when navigating between already-completed steps
- `startOver()` still resets everything correctly
