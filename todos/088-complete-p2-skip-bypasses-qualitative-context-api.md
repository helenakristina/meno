---
status: pending
priority: p2
issue_id: "088"
tags: [code-review, frontend, backend, state-management, data-integrity]
dependencies: []
---

# `handleSkip` in Step3Qualitative bypasses the API call — stale data poisons PDF

## Problem Statement

`handleSkip` advances the wizard without calling `PUT /{id}/qualitative-context`. If a user previously ran the flow and saved partial qualitative data, then starts a new session on the same `appointment_id` and clicks Skip, the old values (`what_have_you_tried`, `specific_ask`, etc.) persist in the DB and silently influence the provider summary PDF — without the user knowing.

This was flagged by three reviewers (TypeScript, architecture, agent-native) and is a correctness bug in a medically-sensitive document.

## Findings

- **File**: `frontend/src/routes/(app)/appointment-prep/Step3Qualitative.svelte`, lines 47–54
- `handleNext` correctly calls `PUT /qualitative-context` with the user's values (or nulls)
- `handleSkip` calls `onNext` directly with all-null payload, never touching the API
- The backend `generate_pdf` reads these four fields at `appointment.py:576–579` and passes them to the LLM prompt
- An agent calling the API directly always sends explicit nulls — UI skip creates a behavioral divergence

## Proposed Solution

```typescript
async function handleSkip() {
  isSaving = true;
  const nullPayload = {
    what_have_you_tried: null,
    specific_ask: null,
    history_clotting_risk: null,
    history_breast_cancer: null,
  };
  try {
    await apiClient.put(
      `/api/appointment-prep/${appointmentId}/qualitative-context` as "/api/appointment-prep/{id}/qualitative-context",
      nullPayload,
    );
    onNext(nullPayload);
  } catch {
    onNext(nullPayload); // still advance; qualitative context is non-critical
  } finally {
    isSaving = false;
  }
}
```

Also: add `disabled={isSaving}` to the Skip button to prevent the skip-during-save double-advance race.

## Acceptance Criteria

- [ ] `handleSkip` calls `PUT /qualitative-context` with all-null payload before calling `onNext`
- [ ] Skip button is `disabled={isSaving}` to prevent double-advance
- [ ] Skip on a resumed session overwrites any previously stored qualitative context with nulls
- [ ] Test: `handleSkip` results in API call with all-null fields
