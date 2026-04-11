---
name: Verify Narrative Editing Endpoint Exists
status: complete
priority: p3
tags: [code-review, api, agent-native]
dependencies: []
---

## Problem Statement

The narrative editing capability may not be exposed via API endpoint, creating an agent-native parity gap.

## Findings

**From:** agent-native-reviewer

**Observation:** The `save_narrative` method exists in the repository layer, but there's no corresponding HTTP route exposed for editing the narrative after it's generated.

**Current state:**

- Repository: `appointment_repository.py` has `save_narrative()`
- Service: May have the method but no route exposed
- UI: May allow editing the narrative in Step 2

## Proposed Solutions

### Option A: Add PUT Endpoint (if UI allows editing)

**Effort:** Small

Add `PUT /api/appointment-prep/{id}/narrative` endpoint if the UI allows users to edit the generated narrative.

### Option B: Confirm No Editing (if UI is read-only)

**Effort:** None

If the UI shows the narrative as read-only, no action needed.

## Recommended Action

Verify if Step 2 allows narrative editing in the UI. If yes, add the endpoint.

## Technical Details

**Files to check:**

- Frontend Step 2 implementation
- `backend/app/api/routes/appointment.py`

## Acceptance Criteria

- [ ] Verified if UI allows narrative editing
- [ ] If yes, PUT endpoint added
- [ ] If no, document the read-only design decision

## Work Log

| Date       | Action                           | Result  |
| ---------- | -------------------------------- | ------- |
| 2026-03-31 | Created from agent-native review | Pending |
