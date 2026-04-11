---
status: complete
priority: p3
issue_id: "110"
tags: [code-review, frontend, appointment-prep, typescript, cleanup]
---

# Minor cleanup batch: appointment prep state persistence

## Problem Statement

Several small quality issues in the appointment prep state persistence changes. None are bugs. Batched here to avoid cluttering the todo list with trivial items.

## Findings

### A — `onChange` prop type has redundant `| null`

**File:** `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte` line 19

```ts
onChange?: ((concerns: Concern[]) => void) | null;
```

The `?` already makes the prop optional (`undefined` when omitted). The `| null` alongside `?` is redundant — optional chaining `onChange?.(updated)` handles both `undefined` and `null`. The default `= null` in destructuring can also be dropped since `undefined` behaves identically.

Fix: `onChange?: (concerns: Concern[]) => void;` and remove `= null` from destructuring.

---

### B — Optional props missing `?` in type annotation

**Files:** `Step1Context.svelte:22`, `Step3Qualitative.svelte:13`

```ts
existingContext: AppointmentContext | null; // should be existingContext?: AppointmentContext | null
existingQualitativeContext: QualitativeContext | null; // same
```

The props have defaults (`= null`) in destructuring, making them optional at call sites. The type annotation doesn't reflect this with `?`. IDE users won't see autocomplete indicating the prop is optional.

Fix: add `?` to optional prop type annotations.

---

### C — `initialConcerns` naming inconsistency

**File:** `Step3Prioritize.svelte`

All other step components use `existing*` prefix for restored state props (`existingContext`, `existingNarrative`, `existingQualitativeContext`). Step3Prioritize uses `initialConcerns`, which implies a seed/default rather than restored data. Should be `existingConcerns` for consistency.

Note: This requires updating the call site in `+page.svelte` as well.

---

### D — Template string cast needs explanatory comment

**Files:** `Step3Qualitative.svelte:37-39,62-64`, `Step3Prioritize.svelte:113-115`

```ts
await apiClient.put(
  `/api/appointment-prep/${appointmentId}/qualitative-context` as "/api/appointment-prep/{id}/qualitative-context",
  payload,
);
```

The cast is necessary because the typed client uses static string literal keys and can't match dynamic interpolated strings. This is a legitimate workaround but looks like a suspicious cast to a future reader. Add a one-line comment explaining the pattern.

---

### E — `goBack` step arithmetic cast is unsafe

**File:** `+page.svelte:129`

```ts
state.currentStep = (state.currentStep - 1) as 1 | 2 | 3 | 4 | 5 | 6;
```

The cast silences the TypeScript error but doesn't prevent a `0` value if the guard is ever bypassed. The guard `if (state.currentStep > 1)` makes this safe today, but the cast remains a code smell.

Better: `const next = state.currentStep - 1; if (next >= 1) { state.currentStep = next as 1 | 2 | 3 | 4 | 5 | 6; }` — though given `currentStep` is typed in `AppointmentPrepState`, a cleaner long-term fix is typing it as `number` and validating at boundaries.

---

## Acceptance Criteria

- [ ] `onChange` type annotation has no redundant `| null`
- [ ] Optional props in step components use `?` in their type annotations
- [ ] `initialConcerns` renamed to `existingConcerns` in Step3Prioritize (and call site)
- [ ] Template string casts have a one-line explanatory comment
- [ ] `goBack` step arithmetic is safe against accidentally producing step `0`

## Work Log

- 2026-04-11: Compiled from TypeScript reviewer + simplicity reviewer + architecture reviewer agents during code review of commits ef9745f/13f72a6
