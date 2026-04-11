---
status: pending
priority: p2
issue_id: "101"
tags: [code-review, frontend, appointment-prep, state-management, health-data]
---

# Step3Qualitative loses sensitive fields on back-navigation

## Problem Statement

`Step3Qualitative.svelte` does not accept an `existingQualitativeContext` prop from the parent orchestrator. When the user completes Step 4 (qualitative context), navigates back, and then navigates forward again, the component mounts fresh with no restored state. The radio buttons for `history_clotting_risk` and `history_breast_cancer` reset to their default values. The user sees an empty form and may believe their answers were lost.

This is a data trust issue for sensitive health fields. The pattern to fix it was established in the same commit that introduced this regression gap (adding `existingNarrative` / `existingScenarios` props to Step2 and Step4) — Step3Qualitative simply wasn't included.

## Findings

- **Discovered by:** TypeScript reviewer (Issue #3) and Security reviewer (P2-B) during code review of commit `13f72a6`
- **Affected file:** `frontend/src/routes/(app)/appointment-prep/Step3Qualitative.svelte`
- **Affected parent:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` — passes no `qualitativeContext` prop to `Step3Qualitative`
- **State field:** `AppointmentPrepState.qualitativeContext: QualitativeContext | null` — already populated after user completes Step 4
- **Sensitive fields affected:** `history_clotting_risk`, `history_breast_cancer` — medical history

## Proposed Solutions

### Option A: Follow the same pattern as Step2Narrative and Step4Scenarios (Recommended)
- Add `existingQualitativeContext: QualitativeContext | null = null` prop to `Step3Qualitative`
- Initialize local state from prop values
- Pass `qualitativeContext={state.qualitativeContext}` from parent
- Effort: Small | Risk: Low

### Option B: Lift qualitative fields into parent state reactively
- Replace `Step3Qualitative`'s local state with props that the parent controls directly
- More invasive, not consistent with how other steps work
- Effort: Medium | Risk: Medium

## Acceptance Criteria
- [ ] Navigating back from Step 5 to Step 4 shows the previously answered qualitative context fields, not blank radio buttons
- [ ] `history_clotting_risk` and `history_breast_cancer` selections are preserved across back-navigation
- [ ] Page refresh at Step 4 restores the qualitative context answers

## Work Log
- 2026-04-11: Found during code review of commit 13f72a6 (appointment prep state persistence fix)
