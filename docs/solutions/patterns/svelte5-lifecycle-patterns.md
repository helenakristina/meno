# Svelte 5 Lifecycle Patterns: sessionStorage, $effect, and onMount

Patterns discovered during the Meno appointment prep state persistence implementation.
These are compiler-silent gotchas that caused real bugs.

---

## Pattern 1: `$effect` fires before `onMount` — race with sessionStorage

In Svelte 5, `$effect` runs synchronously during component initialization after the
first render, **before `onMount`**. Any `$effect` that writes to sessionStorage will
overwrite values that `onMount` hasn't had a chance to restore yet.

### Anti-pattern

```typescript
// WRONG: $effect fires before onMount, overwrites restored state
$effect(() => {
  sessionStorage.setItem("myState", JSON.stringify(state));
});
onMount(() => {
  const saved = sessionStorage.getItem("myState");
  if (saved) state = JSON.parse(saved); // never reached — $effect already overwrote it
});
```

The `$effect` block tracks `state`, so it fires as part of initialization. By the
time `onMount` runs, the previously persisted value has already been replaced with
the component's initial state.

### Fix

Use explicit save calls (not `$effect`) for sessionStorage writes. Initialize from
sessionStorage inside `onMount` only.

```typescript
// CORRECT: no $effect for persistence — explicit calls only
onMount(() => {
  const saved = sessionStorage.getItem("myKey");
  if (saved) state = JSON.parse(saved);
});

function saveToSession() {
  sessionStorage.setItem("myKey", JSON.stringify(state));
}
// Call saveToSession() explicitly after any mutation that should be persisted
```

### Why this matters

This ordering (`$effect` before `onMount`) differs from what Svelte 4 `$: reactive`
statements implied, and the Svelte 5 compiler gives no warning. The bug silently
discards restored state on every page load.

---

## Pattern 2: sessionStorage sole-writer pattern in multi-step flows

When a parent component owns sessionStorage and child step components receive data
via props, the **parent must be the sole writer**. Child components that read their
own prop values and re-persist them create a race with parent initialization: the
child's write can land before or after the parent's restore, producing inconsistent
state.

The child's persistence should only happen via callbacks that the parent controls.

### Parent: sole owner of sessionStorage

```typescript
// +page.svelte (parent)
onMount(() => {
  const saved = sessionStorage.getItem("appointmentPrepState");
  if (saved) state = JSON.parse(saved);
});

function handleConcernsChange(concerns: Concern[]) {
  state.concerns = concerns;
  saveToSession(); // parent is the only caller of sessionStorage.setItem
}

function saveToSession() {
  sessionStorage.setItem("appointmentPrepState", JSON.stringify(state));
}
```

### Child: fires callback, never writes sessionStorage directly

```typescript
// Step3Concerns.svelte (child)
let { existingConcerns = [], onChange } = $props();

function updateConcern(updated: Concern[]) {
  concerns = updated;
  onChange?.(updated); // parent decides when and whether to persist
}
```

### Why this matters

Multi-step wizard flows often have one parent coordinating several step components.
If a step component writes to the same sessionStorage key the parent manages, there
is no guaranteed ordering between the child's write and the parent's `onMount`
restore. Centralizing writes in the parent eliminates the race entirely.

---

## Pattern 3: LLM API call guard in `onMount`

Step components that call an LLM API in `onMount` must check whether the data they
need already exists (passed as a prop from the parent's restored state) before
making the call. Without this guard, every page reload triggers an expensive LLM
call even when the result was already persisted to sessionStorage.

### Anti-pattern

```typescript
// WRONG: always calls LLM even when restored state already has the result
onMount(async () => {
  const result = await callLLM(appointmentId);
  narrative = result;
});
```

### Fix

```typescript
// CORRECT: skip LLM call when a restored result is already available
let { existingNarrative = null } = $props();

onMount(async () => {
  if (existingNarrative !== null) return; // restored from session — skip LLM
  const result = await callLLM(appointmentId);
  narrative = result;
});
```

### Why this matters

LLM calls are slow and cost money. In a multi-step flow where the user can navigate
back and forward, the step component mounts multiple times. A missing guard means
redundant API calls on every remount — including cases where the user just pressed
the back button and immediately moved forward again. The prop-based guard lets the
parent communicate "I already have this, don't fetch again."

---

## Keywords

effect, onMount, sessionStorage, LLM guard, lifecycle, race condition, multi-step wizard
