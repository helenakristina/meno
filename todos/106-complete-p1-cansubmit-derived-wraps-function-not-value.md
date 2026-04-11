---
status: complete
priority: p1
issue_id: "106"
tags: [code-review, frontend, appointment-prep, svelte5, reactivity, bug]
---

# `$derived(() => {})` wraps a function — submit button not reactive

## Problem Statement

In `Step1Context.svelte`, `canSubmit` is declared as `$derived(() => { ... })`. This makes `canSubmit` a stable function reference (the derivation never changes), not a reactive boolean. Svelte's reactivity system never re-evaluates it when `$formData` changes because the derived value is the function itself — which is always the same function.

The call sites `disabled={!canSubmit()}` and `aria-disabled={!canSubmit()}` invoke the function at render time and get the correct boolean, but the bindings will not re-run when `$formData` changes. In practice: the user selects a radio button, the form becomes valid, but the submit button remains disabled until something else triggers a re-render.

This is a silent reactivity breakage — the button appears disabled to users who complete the form correctly.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/Step1Context.svelte` line 46
- **Current code:**
  ```ts
  let canSubmit = $derived(() => {
    const hasRequired =
      !!$formData.appointment_type &&
      !!$formData.goal &&
      !!$formData.dismissed_before;
    const urgentSymptomValid = showUrgentSymptomField
      ? !!$formData.urgent_symptom?.trim()
      : true;
    return hasRequired && urgentSymptomValid;
  });
  ```
- **Usage sites:** `handleNext` (line 54), `disabled={!canSubmit()}` (line 179), `aria-disabled={!canSubmit()}` (line 181)
- **Why it works sometimes:** On first render, calling `canSubmit()` returns the current value. But subsequent changes to `$formData` don't trigger re-evaluation because Svelte tracks the reactive dependencies of the `$derived` expression, and the expression is `() => { ... }` — a function literal that reads no reactive values at derivation time.

## Proposed Solutions

### Option A: Remove the function wrapper (Recommended)

Make `$derived` compute the boolean directly:

```ts
let canSubmit = $derived(
  !!$formData.appointment_type &&
    !!$formData.goal &&
    !!$formData.dismissed_before &&
    (showUrgentSymptomField ? !!$formData.urgent_symptom?.trim() : true),
);
```

Then remove call parens everywhere: `disabled={!canSubmit}`, `aria-disabled={!canSubmit}`, `if (!canSubmit) return`.

- Effort: XS | Risk: None

### Option B: Use `$derived.by()` for multi-line logic

```ts
let canSubmit = $derived.by(() => {
  const hasRequired =
    !!$formData.appointment_type &&
    !!$formData.goal &&
    !!$formData.dismissed_before;
  const urgentSymptomValid = showUrgentSymptomField
    ? !!$formData.urgent_symptom?.trim()
    : true;
  return hasRequired && urgentSymptomValid;
});
```

`$derived.by()` is the correct Svelte 5 API for multi-line derived computations. It executes the function and tracks reactive dependencies properly, unlike `$derived(() => {})` which treats the function as the value.

- Effort: XS | Risk: None

## Acceptance Criteria

- [ ] Selecting all required radio buttons in Step 1 enables the Next button without requiring any other interaction
- [ ] `canSubmit` is a `boolean`, not a `() => boolean`
- [ ] No call parens at usage sites

## Work Log

- 2026-04-11: Found during code review of commits ef9745f/13f72a6 by TypeScript reviewer agent
