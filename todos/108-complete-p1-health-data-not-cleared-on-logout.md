---
status: complete
priority: p1
issue_id: "108"
tags: [code-review, frontend, appointment-prep, security, health-data, auth]
---

# Health data not cleared from sessionStorage on logout

## Problem Statement

`handleLogout()` in `+layout.svelte` calls `supabase.auth.signOut()` and redirects to `/login`. It does not clear `appointmentPrepState` from sessionStorage. After logout, the full wizard state — including `narrative` (user-written health summary), `qualitativeContext` (clotting risk, breast cancer history, treatments tried), and `concerns` (prioritized medical concerns) — remains readable in sessionStorage.

The next person to open the same browser and navigate to `/appointment-prep` will have `onMount` fire, find the key, restore the prior user's medical session, and see the "Resume Previous Session?" prompt with the previous user's step count. This is a concrete risk for shared computers (clinic waiting rooms, shared family devices, work machines).

Note: **Todo 104 (unscoped key)** addresses the cross-user exposure by namespacing the key with user ID. This todo is a separate defense-in-depth: even with a namespaced key, clearing on logout prevents medical data from lingering in browser storage after the user explicitly signs out.

**Priority for dev POC:** P1 (this is a health app with sensitive medical data, even in dev the principle should be correct). Fix before any external testing or sharing.

## Findings

- **File:** `frontend/src/routes/(app)/+layout.svelte` — `handleLogout()` function
  - Current: calls `supabase.auth.signOut()` + redirect, no sessionStorage cleanup
- **Data at risk:** `sessionStorage.getItem('appointmentPrepState')` contains:
  - `narrative`: LLM-generated + user-edited health narrative
  - `qualitativeContext.history_clotting_risk`, `history_breast_cancer`: medical history enums
  - `qualitativeContext.what_have_you_tried`: user-written treatment history
  - `concerns[]`: prioritized medical concerns with user comments

## Proposed Solutions

### Option A: Clear in `handleLogout()` directly (Recommended)

```ts
function handleLogout() {
  sessionStorage.removeItem("appointmentPrepState");
  await supabase.auth.signOut();
  goto("/login");
}
```

Simple, explicit, co-located with the logout action.

- Effort: XS | Risk: None

### Option B: Hook into `onAuthStateChange` for SIGNED_OUT

In the layout's auth setup:

```ts
supabase.auth.onAuthStateChange((event) => {
  if (event === "SIGNED_OUT") {
    sessionStorage.removeItem("appointmentPrepState");
  }
});
```

More robust: catches logout from any path (token expiry, sign-out from another tab). But more implicit.

- Effort: Small | Risk: Low

### Option C: Combine A + B

Do both: explicit clear in `handleLogout()` + `onAuthStateChange` listener as a fallback for token expiry.

- Effort: Small | Risk: None — belt and suspenders for a health app.

## Acceptance Criteria

- [ ] After `handleLogout()`, `sessionStorage.getItem('appointmentPrepState')` returns `null`
- [ ] Navigating to `/appointment-prep` after logout shows a fresh wizard, not the previous user's session
- [ ] Token expiry / session timeout also clears the storage (Option B/C)

## Work Log

- 2026-04-11: Found during code review by security reviewer agent. Related to todo 104 (unscoped key) — both should be fixed together.
