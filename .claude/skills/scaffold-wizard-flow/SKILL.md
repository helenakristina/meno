---
name: scaffold-wizard-flow
description: >
  Pattern for building multi-step wizard flows in SvelteKit with Svelte 5 runes.
  Use when building a new multi-step form, onboarding flow, or any sequential
  UI with shared state across steps. Reference implementation: appointment-prep/.
---

# Scaffold Wizard Flow

Reference implementation: `frontend/src/routes/(app)/appointment-prep/`

Read that code first. This skill describes the pattern it implements.

## Structure

```
routes/(app)/[feature]/
├── +page.svelte          ← Orchestrator: owns all state, renders current step
├── Step1.svelte          ← Dumb step: receives props, calls onNext()
├── Step2.svelte
└── ...
```

## Orchestrator Rules

The orchestrator owns everything. Steps own nothing.

```svelte
<script lang="ts">
  // All flow state in one typed object — never distributed across stores
  let flowState = $state<FlowState>({
    step: 1 as 1 | 2 | 3 | 4 | 5,  // Literal union, not number
    stepOneData: null,
    stepTwoData: null,
    // ...
  });

  function handleNext(data: StepOneData) {
    flowState.stepOneData = data;
    flowState.step = 2;
  }

  function handleBack() {
    flowState.step -= 1;  // Never clears data, never validates
  }
</script>

{#if flowState.step === 1}
  <StepOne data={flowState.stepOneData} onNext={handleNext} onBack={handleBack} />
{:else if flowState.step === 2}
  ...
{/if}

<progress
  role="progressbar"
  aria-valuenow={flowState.step}
  aria-valuemin={1}
  aria-valuemax={5}
  value={flowState.step}
  max={5}
/>
```

## Step Rules

Steps are dumb. They receive data, render UI, emit events.

```svelte
<script lang="ts">
  interface Props {
    data: StepOneData | null;
    onNext: (result: StepOneData) => void;
    onBack: () => void;
  }
  let { data, onNext, onBack } = $props<Props>();

  // Each step manages its own loading/error state
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  async function handleSubmit() {
    isLoading = true;
    error = null;
    try {
      const result = await doStepWork();
      onNext(result);  // Hand off to orchestrator
    } catch (err) {
      error = err instanceof Error ? err.message : 'Something went wrong';
      // Retry here — never force backward navigation on failure
    } finally {
      isLoading = false;
    }
  }
</script>
```

## Key Rules

- **Step numbers are literal unions** (`1 | 2 | 3`), not plain `number` — catches
  invalid step values at compile time
- **Back navigation never clears data, never validates** — user can go back and
  return without losing work
- **Retry at step level** — a failed LLM call in step 3 shows a retry button in
  step 3, not a redirect to step 1
- **Persist to sessionStorage** when any step makes an expensive call (LLM, upload)
  so a refresh doesn't lose progress
- **Anti-pattern:** distributing state across multiple stores or letting steps own
  their own persistent state — makes back-navigation and reset painful
