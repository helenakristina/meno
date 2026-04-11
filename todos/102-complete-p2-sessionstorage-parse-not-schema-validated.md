---
status: complete
priority: p2
issue_id: "102"
tags: [code-review, frontend, appointment-prep, security, data-integrity]
---

# sessionStorage parse is not schema-validated before assignment

## Problem Statement

In `+page.svelte` `onMount`, the restored sessionStorage value is parsed with `JSON.parse` and assigned directly to `state` without validating that it conforms to `AppointmentPrepState`. Corrupt or stale JSON (from a browser extension, a different app version, or a tab writing to the same key) can silently replace the component's state with malformed data.

Specifically: a corrupt `currentStep` value (e.g., `999`) would cause all `{#if state.currentStep === N}` branches to fail — rendering a blank page with no error. A partial `qualitativeContext` could silently drop `history_breast_cancer` data before it reaches the backend.

## Findings

- **Discovered by:** Security reviewer (P2-A) during code review of commit `13f72a6`
- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` lines 48–58
- **Current code:**
  ```typescript
  const parsed = JSON.parse(saved);
  state = parsed;  // no validation
  ```
- **Risk:** Silent data integrity failure in a medical context. Not an injection vector (user-controlled data only) but can silently drop health fields before they reach the backend.

## Proposed Solutions

### Option A: Lightweight type guard (Recommended)
Write a `isAppointmentPrepState(v: unknown): v is AppointmentPrepState` guard that checks the critical fields (`currentStep` in `[1..6]`, `appointmentId` is string or null, etc.). Fall back to default state if guard fails.
- Effort: Small | Risk: Low

### Option B: Zod schema validation
Add `AppointmentPrepStateSchema` using Zod. Parse with `.safeParse()` and fall back to default on failure.
- Effort: Small-Medium | Risk: Low — adds Zod dependency if not already used in frontend

### Option C: Versioned state with migration
Add a `version` field to the serialized state. On restore, check version and migrate or discard if incompatible.
- Effort: Medium | Risk: Low — most robust for future schema changes

## Acceptance Criteria
- [ ] Corrupted sessionStorage (invalid JSON, wrong shape, out-of-range `currentStep`) falls back to the default initial state rather than crashing or showing a blank page
- [ ] Health fields (`qualitativeContext`, `narrative`) are validated as the correct type or reset to null on restore failure
- [ ] A console warning is logged when saved state fails validation (no user-facing PII)

## Work Log
- 2026-04-11: Found during code review of commit 13f72a6
