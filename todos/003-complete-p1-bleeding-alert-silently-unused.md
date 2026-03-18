---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, frontend, medical-boundary]
dependencies: []
---

# Wire `bleedingAlert` in `handleSave` — post-save alert never shown

## Problem Statement

`PeriodLogModal.svelte` calls `onSave(log, bleedingAlert)` and the parent page's `handleSave` signature accepts `(log: PeriodLog, bleedingAlert: boolean)` — but the `bleedingAlert` parameter is never used in the parent. When a post-menopausal user logs a period and the backend returns `bleeding_alert: true`, the safety advisory is shown inside the modal, but once the modal closes after save, the alert is silently dropped. The parent page has no record of it.

This is a medical boundary concern: the postmenopausal bleeding alert is important health information that should persist visibly after logging.

## Findings

- `frontend/src/routes/(app)/period/+page.svelte:89-97` — `handleSave` declares `bleedingAlert: boolean` but never uses it
- `frontend/src/lib/components/period/PeriodLogModal.svelte` — calls `onSave(log, bleedingAlert)` after save
- Modal closes after save, so any in-modal alert is dismissed immediately
- TypeScript reviewer flagged: "bleeding alert silently dropped"

## Proposed Solutions

### Option 1: Show alert banner on period page after modal closes

**Approach:**
1. Add `bleedingAlertActive = $state(false)` to the period page
2. In `handleSave`, set `bleedingAlertActive = bleedingAlert`
3. Render an amber advisory banner on the page when `bleedingAlertActive` is true
4. Include a dismiss button to clear `bleedingAlertActive`

```svelte
// +page.svelte
let bleedingAlertActive = $state(false);

function handleSave(log: PeriodLog, bleedingAlert: boolean) {
  // existing log update logic...
  if (bleedingAlert) bleedingAlertActive = true;
}
```

**Pros:** Alert persists after modal close, consistent with inference banner pattern already on the page

**Cons:** Adds state to the page

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Keep alert inside modal, delay close

**Approach:** When `bleedingAlert` is true after save, delay the modal close by showing the alert with a required acknowledgement button before closing.

**Pros:** Alert is contextually tied to the logging action

**Cons:** Blocks the user from continuing; alert still lost after acknowledgement

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1. Matches the existing inference banner pattern on the page, keeps the alert visible without blocking the user.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/period/+page.svelte:89-97` — `handleSave` function
- `frontend/src/routes/(app)/period/+page.svelte` — template, add banner render

## Acceptance Criteria

- [ ] When backend returns `bleeding_alert: true`, a visible advisory banner appears on the period page after modal close
- [ ] Banner includes the advisory text matching the project's medical boundary guidelines
- [ ] Banner has a dismiss button
- [ ] Banner does not appear when `bleeding_alert` is false

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Traced bleedingAlert through modal → onSave → handleSave
- Confirmed it is silently dropped
