---
status: pending
priority: p2
issue_id: "103"
tags: [code-review, frontend, appointment-prep, ux, state-management]
---

# isLoading and error are serialized to sessionStorage, causing stale state on resume

## Problem Statement

`saveToSession()` serializes the entire `AppointmentPrepState` object, including `isLoading: boolean` and `error: string | null`. If a session ends with a failed API call (`error: "Failed to generate narrative. Please try again."`) or mid-request (`isLoading: true`), the next session will restore with that stale error banner or loading overlay shown immediately on page load.

In a health app, stale error messages from a previous session are confusing and erode trust. The loading overlay rendering on resume is a functional defect.

## Findings

- **Discovered by:** Security reviewer (P3-B) during code review of commit `13f72a6`
- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte`
- **`saveToSession()`** serializes all fields including transient UI state
- **`onMount` restore** assigns the full parsed object including `isLoading` and `error`

## Proposed Solutions

### Option A: Strip transient fields before saving (Recommended)
In `saveToSession()`, explicitly omit `isLoading` and `error`:
```typescript
function saveToSession() {
  const { isLoading, error, ...persistable } = state;
  sessionStorage.setItem('appointmentPrepState', JSON.stringify(persistable));
}
```
And in `onMount`, always reset them to their defaults after restore:
```typescript
state = { ...parsed, isLoading: false, error: null };
```
- Effort: Small | Risk: Low

### Option B: Reset transient fields only on restore
Keep `saveToSession()` unchanged. In `onMount`, set `state.isLoading = false; state.error = null` after restoring.
- Effort: Tiny | Risk: Low — simpler but still serializes transient fields unnecessarily

## Acceptance Criteria
- [ ] Restoring a session that ended with an error does not show the error banner
- [ ] Restoring a session that was mid-load does not show the loading overlay
- [ ] All other state (step, narrative, concerns, scenarios) still restores correctly

## Work Log
- 2026-04-11: Found during code review of commit 13f72a6
