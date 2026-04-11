---
status: pending
priority: p3
issue_id: "094"
tags: [code-review, frontend, accessibility, testing]
dependencies: []
---

# Frontend nitpicks: missing key on sources, false-green test, role=dialog misuse

## Problem Statement

Four small frontend issues found in the PR, none blocking individually.

## Findings

### 1. Missing `{#each}` key on `card.sources` — Step4Scenarios.svelte line 93

```svelte
{#each card.sources as source}  <!-- missing key -->
```

Fix: `{#each card.sources as source (source.title)}`

### 2. Progress percent test still uses 5-step divisor — `appointment-prep.test.ts` lines 446–458

```ts
const percent = (step / 5) * 100; // component uses / 6
```

The test is testing its own formula, not the component's. Step 6 should be 100%, step 1 ~16.7%. Update the test cases and divisor to match 6 steps.

### 3. `role="dialog"` misused on resume banner — `+page.svelte` line 214

```svelte
<div role="dialog" class="mb-6 rounded-lg ...">
```

`role="dialog"` requires focus trapping and `aria-modal`. This is inline content. Change to `role="region" aria-label="Resume previous session"` or remove the role entirely.

### 4. Back navigation discards concern edits — `+page.svelte` + `Step3Prioritize.svelte`

`Step3Prioritize` initialises concerns from `DEFAULT_CONCERNS[goal]` on mount, not from the parent's `state.concerns`. When the user navigates Back from step 4, their edited concern list is lost. Fix: pass `initialConcerns={state.concerns}` as a prop and use it as the initial value if non-empty.

## Acceptance Criteria

- [ ] `{#each card.sources as source (source.title)}` in Step4Scenarios
- [ ] Progress test updated to use 6-step divisor and correct expected values
- [ ] Resume banner uses `role="region"` or no role
- [ ] Step3Prioritize accepts and uses `initialConcerns` prop to preserve edits on back-navigation
