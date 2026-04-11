---
status: complete
priority: p3
issue_id: "117"
tags: [code-review, frontend, cleanup, appointment-prep]
---

# `validSteps` array recreated on every `isValidAppointmentPrepState` call

## Problem Statement

`const validSteps = [1, 2, 3, 4, 5, 6]` inside `isValidAppointmentPrepState` allocates a new array on each call. While this function is only called once (in `onMount`), the intent is a fixed constant — it should be declared at module level.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` line ~53

## Proposed Solution

```ts
const VALID_STEPS = [1, 2, 3, 4, 5, 6] as const;

function isValidAppointmentPrepState(v: unknown): v is AppointmentPrepState {
    // ...
    return VALID_STEPS.includes(s.currentStep as 1 | 2 | 3 | 4 | 5 | 6);
}
```

- Effort: XS | Risk: None

## Work Log
- 2026-04-11: Found during performance review of commit e690800
