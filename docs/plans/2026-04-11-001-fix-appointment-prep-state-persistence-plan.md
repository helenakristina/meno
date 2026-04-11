---
title: "fix: Appointment Prep State Lost on Back Navigation and Page Refresh"
type: fix
status: completed
date: 2026-04-11
origin: docs/brainstorms/2026-04-11-appointment-prep-state-persistence-brainstorm.md
---

# fix: Appointment Prep State Lost on Back Navigation and Page Refresh

## Overview

In the appointment prep multi-step flow, pressing Back and refreshing the page both wipe all previously generated content and user edits. Users must restart from scratch. Two distinct bugs cause this — one in the orchestrator's state persistence approach, one in individual step components.

## Problem Statement

### Bug 1 — `$effect` races with `onMount` and overwrites sessionStorage

In Svelte 5, `$effect` runs after the initial render, **before** `onMount`. The current orchestrator (`+page.svelte`) uses `$effect` to persist state to sessionStorage. On every page load the sequence is:

1. Component initializes with empty `AppointmentPrepState` (`appointmentId: null`, etc.)
2. `$effect` fires → serializes empty state → **overwrites** any previously saved data in sessionStorage
3. `onMount` fires → reads sessionStorage → finds the empty state that was just written

The saved state is destroyed on every load. This is why page refresh loses everything.

### Bug 2 — Step components unconditionally call LLM APIs on mount

`Step2Narrative.svelte` and `Step4Scenarios.svelte` both fire their API (POST) calls in `onMount` regardless of whether the parent orchestrator already has the data in `state`. The parent passes `appointmentId` but not the existing generated content, so step components have no way to skip regeneration.

Even if Bug 1 were fixed, navigating Back → Forward would still re-trigger expensive LLM calls and overwrite user edits.

**Steps affected by Bug 2:**

| Step          | Component                 | Calls API on mount?            | Action needed |
| ------------- | ------------------------- | ------------------------------ | ------------- |
| 2             | `Step2Narrative.svelte`   | ✅ Yes — `POST .../narrative`  | Add guard     |
| 3 Prioritize  | `Step3Prioritize.svelte`  | No — local reordering only     | None          |
| 3 Qualitative | `Step3Qualitative.svelte` | No — saves on button press     | None          |
| 4             | `Step4Scenarios.svelte`   | ✅ Yes — `POST .../scenarios`  | Add guard     |
| 5             | `Step5Generate.svelte`    | No — generates on button press | None          |

## Proposed Solution

### Fix 1 — Remove `$effect`, use explicit `saveToSession()` calls

Remove the reactive `$effect(() => sessionStorage.setItem(...))` from `+page.svelte` entirely. Replace it with a `saveToSession()` helper that is called explicitly at every state transition.

```typescript
// +page.svelte

// Remove this:
// $effect(() => {
//   sessionStorage.setItem('appointmentPrepState', JSON.stringify(state));
// });

// Add this helper:
function saveToSession() {
  sessionStorage.setItem("appointmentPrepState", JSON.stringify(state));
}
```

Call `saveToSession()` at the end of every handler that transitions state:

- `handleStep1` — after `state.currentStep = 2`
- `handleStep2` — after `state.currentStep = 3`
- `handleStep3` — after `state.currentStep = 4`
- `handleStep3Qualitative` — after `state.currentStep = 5`
- `handleStep4` — after `state.currentStep = 6`
- `goBack()` — after decrementing `state.currentStep`

The `onMount` load stays unchanged — it already works correctly once `$effect` stops overwriting the saved data.

### Fix 2 — Pass existing data as props; guard API calls in step components

**`+page.svelte` — pass existing data to affected steps:**

```svelte
<!-- Step 2: pass existing narrative -->
<Step2Narrative
  appointmentId={state.appointmentId!}
  existingNarrative={state.narrative}
  onNext={handleStep2}
/>

<!-- Step 4: pass existing scenarios -->
<Step4Scenarios
  appointmentId={state.appointmentId!}
  existingScenarios={state.scenarios}
  onNext={handleStep4}
/>
```

**`Step2Narrative.svelte` — accept `existingNarrative` prop, skip generation if present:**

```typescript
let {
  appointmentId,
  existingNarrative = null, // NEW
  onNext,
}: {
  appointmentId: string;
  existingNarrative: string | null;
  onNext: (narrative: string) => void;
} = $props();

let narrative = $state(existingNarrative ?? "");
let isLoading = $state(existingNarrative === null); // only show spinner if fetching

onMount(() => {
  if (existingNarrative !== null) return; // skip — already have it
  loadNarrative();
});
```

**`Step4Scenarios.svelte` — accept `existingScenarios` prop, skip generation if present:**

```typescript
let {
  appointmentId,
  existingScenarios = [], // NEW
  onNext,
}: {
  appointmentId: string;
  existingScenarios: ScenarioCard[];
  onNext: (scenarios: ScenarioCard[]) => void;
} = $props();

let scenarios = $state<ScenarioCard[]>(existingScenarios);
let isLoading = $state(existingScenarios.length === 0); // only show spinner if fetching

onMount(() => {
  if (existingScenarios.length > 0) return; // skip — already have them
  loadScenarios();
});
```

## Technical Considerations

- **SSR safety:** `sessionStorage` is only available in the browser. The existing `onMount` for loading already handles this correctly. No changes to SSR behavior.
- **`startOver()` is unaffected:** It already calls `sessionStorage.removeItem('appointmentPrepState')` explicitly — this continues to work.
- **Reactive writes after Fix 1:** All state mutations that previously relied on `$effect` now need an explicit `saveToSession()`. The handlers are the only save points; this is intentional and traceable.
- **`isLoading` initialization:** Step2 and Step4 both initialize `isLoading = true`. With the guard, we must set it to `false` when skipping the API call — handled by initializing from the prop value as shown above.
- **`savedStateExists` flag:** Currently set in `onMount` but unused in the template. Can be removed as cleanup, or left in place — it doesn't affect correctness.

## Files to Change

| File                                                               | Change                                                                                                                                       |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/routes/(app)/appointment-prep/+page.svelte`          | Remove `$effect` save; add `saveToSession()`; call it in all handlers and `goBack()`; pass `existingNarrative` and `existingScenarios` props |
| `frontend/src/routes/(app)/appointment-prep/Step2Narrative.svelte` | Add `existingNarrative` prop; guard `loadNarrative()` call                                                                                   |
| `frontend/src/routes/(app)/appointment-prep/Step4Scenarios.svelte` | Add `existingScenarios` prop; guard `loadScenarios()` call                                                                                   |

No backend changes required.

## Acceptance Criteria

- [ ] Refreshing the page at any step (2–6) restores the user to that step with all previously generated content intact
- [ ] Pressing Back at Step 2–6 shows the previous step's content without regenerating or wiping data
- [ ] Navigating Back then Forward again does not re-trigger any LLM API call (Step 2 narrative, Step 4 scenarios)
- [ ] User edits to the narrative (Step 2) survive Back navigation and page refresh
- [ ] `startOver()` still resets everything and clears sessionStorage correctly
- [ ] No regressions: all existing appointment prep tests pass

## Testing

**Manual test path:**

1. Complete Step 1 → Step 2 (wait for narrative to generate)
2. Edit the narrative text
3. Press Back → confirm Step 1 shows correctly
4. Press Forward → Step 2 shows the edited narrative (no spinner, no regeneration)
5. Continue to Step 4 (scenarios)
6. Press Back → Back → confirm earlier steps show correct content
7. Refresh the page → confirm current step and all generated content are restored

**Unit tests** (if they exist): Run `npm test` and confirm no regressions in appointment prep component tests.

## Dependencies & Risks

- **Risk:** Any step handler that was added later and doesn't call `saveToSession()` will silently break persistence. Mitigation: the plan lists every call site explicitly; a code review check is sufficient.
- **Risk:** If a step component is mounted while `existingNarrative` / `existingScenarios` is `null` due to mid-flow state corruption, it falls back to fetching — same behavior as before, safe.

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-04-11-appointment-prep-state-persistence-brainstorm.md](../brainstorms/2026-04-11-appointment-prep-state-persistence-brainstorm.md)
  - Key decisions carried forward: (1) remove `$effect`, use explicit saves; (2) pass existing data as props to step components; (3) sessionStorage kept (not replaced with module store or DB-backed state)
- Orchestrator: `frontend/src/routes/(app)/appointment-prep/+page.svelte`
- Step 2: `frontend/src/routes/(app)/appointment-prep/Step2Narrative.svelte:19` — `onMount` API call
- Step 4: `frontend/src/routes/(app)/appointment-prep/Step4Scenarios.svelte:19` — `onMount` API call
- Related MEMORY.md entry: "Svelte 5: onMount vs $effect for Data Fetching"
