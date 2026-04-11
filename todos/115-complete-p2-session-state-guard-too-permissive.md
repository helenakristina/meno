---
status: complete
priority: p2
issue_id: "115"
tags: [code-review, frontend, appointment-prep, security, data-integrity, health-data]
---

# `isValidAppointmentPrepState` guard only checks `currentStep` — medical fields unvalidated

## Problem Statement

The type guard in `+page.svelte` accepts any object with `currentStep` in [1..6] as a valid `AppointmentPrepState`. Medical fields like `qualitativeContext.history_clotting_risk`, `qualitativeContext.history_breast_cancer`, and `concerns[]` are restored from sessionStorage without shape or value validation.

In a health app, corrupt or attacker-controlled sessionStorage data (XSS, browser extension, old schema version) flows directly into API calls. A step-3 restore with a malformed `concerns` array will silently send invalid data to the backend, and a step-4 restore with a corrupt `qualitativeContext` could send wrong medical history values.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` lines 50-55
- **Current guard:**
  ```ts
  function isValidAppointmentPrepState(v: unknown): v is AppointmentPrepState {
      if (typeof v !== 'object' || v === null) return false;
      const s = v as Record<string, unknown>;
      const validSteps = [1, 2, 3, 4, 5, 6];
      return validSteps.includes(s.currentStep as number);
  }
  ```
- **Not validated:** `appointmentId` (string when step > 1), `context` (object), `concerns` (array of `{text: string}`), `qualitativeContext` (null or object with string enum fields)

## Proposed Solutions

### Option A: Validate critical fields by step (Recommended)
```ts
function isValidAppointmentPrepState(v: unknown): v is AppointmentPrepState {
    if (typeof v !== 'object' || v === null) return false;
    const s = v as Record<string, unknown>;
    if (![1, 2, 3, 4, 5, 6].includes(s.currentStep as number)) return false;
    // For steps that require appointmentId, validate it's a string
    if ((s.currentStep as number) > 1 && typeof s.appointmentId !== 'string') return false;
    // concerns must be an array if present
    if (s.concerns !== undefined && !Array.isArray(s.concerns)) return false;
    return true;
}
```

### Option B: Accept current guard, add runtime validation at point of use
Validate individual fields before passing them to API calls rather than at restore time. More surgical but less principled.

- Option A effort: Small | Risk: Low

## Acceptance Criteria
- [ ] Restored state with a non-string `appointmentId` when step > 1 falls back to defaults
- [ ] Restored state with a non-array `concerns` field falls back to defaults
- [ ] Valid state still restores correctly

## Work Log
- 2026-04-11: Found during TypeScript and security reviews of commit e690800
