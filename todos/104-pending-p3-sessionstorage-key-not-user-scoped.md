---
status: pending
priority: p3
issue_id: "104"
tags: [code-review, frontend, security, privacy, appointment-prep]
---

# sessionStorage key not user-scoped — shared device privacy leak

## Problem Statement

The sessionStorage key is `'appointmentPrepState'` (a flat string). On a shared device (family computer, clinic kiosk), if user A starts the appointment prep flow and closes the tab without starting fresh, user B opening the appointment prep page will see the resume banner offering to restore user A's session. Clicking "Resume" will show user A's health narrative, concern list, and medical history answers in user B's browser.

The backend correctly enforces ownership (user B cannot submit user A's data — the `user_id` check in `get_context` would 404), but user A's health data is displayed in the UI to user B.

## Findings

- **Discovered by:** Security reviewer (P3-A) during code review of commit `13f72a6`
- **Key:** `'appointmentPrepState'` in `sessionStorage` — no user identifier
- **Impact:** Health data visible to the next user on a shared device
- **Mitigated by:** sessionStorage is tab-scoped (not `localStorage`), so it's cleared when the browser window closes — shared device risk is limited to same-browser-session handoffs

## Proposed Solution

Suffix the key with the authenticated user's ID:
```typescript
const SESSION_KEY = `appointmentPrepState_${userId}`;
```
Where `userId` comes from `$authState.user.id` (available in the `(app)` layout). This scopes the saved state to the specific user and prevents cross-user restore.

- Effort: Small | Risk: Low

## Acceptance Criteria
- [ ] Two different users on the same browser do not see each other's appointment prep state
- [ ] The key includes the user's Supabase user ID
- [ ] `startOver()` and restore logic use the same scoped key

## Work Log
- 2026-04-11: Found during code review of commit 13f72a6
