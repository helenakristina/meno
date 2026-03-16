# Period Tracking Feature — Brainstorm

**Date:** 2026-03-16
**Status:** Draft
**Author:** Helena + Claude

---

## What We're Building

A flexible, optional period tracking system that gives Meno contextual awareness of the user's menstrual cycle — to better understand where they are in their menopause journey, flag medically significant events, and draw patterns that inform the LLM context.

This is **not** a fertility tracker. It is a perimenopause/menopause health tool where bleeding patterns are one important signal among many.

Paired with this: a **general settings page** where users can manage account preferences including the period tracking toggle and their journey stage.

---

## Why This Approach

Period tracking needs to serve two audiences simultaneously:
1. **Users who want simplicity** — just log "my period started today" and move on
2. **Users who want detail** — log flow levels, spotting days, notes, multi-day cycles

A calendar view handles both: it's visual, supports retroactive entry, and lets users see patterns without charts or stats front-and-center.

Journey stage (currently set once at onboarding) needs to become a living, updatable value — both manually (settings) and automatically (12 months without a period = system infers menopause milestone).

---

## Key Decisions

### 1. Period logging is optional
- Stored as a user preference: `period_tracking_enabled` in the `users` table (or a settings table)
- Users who opt out never see period-related UI
- Relevant for: users post-hysterectomy, users on contraception that stops periods, users who find tracking distressing

### 2. Calendar view as the primary interface
- `/period` route with a month-by-month calendar
- Days with period logged are highlighted (color-coded by flow level)
- Click any day to log or edit that day's data
- Can navigate to past months (retroactive logging)

### 3. Flexible data entry — progressive disclosure
- **Minimal:** tap a day → "Period started" toggle → save (just records `period_start`)
- **Optional details:** flow level (spotting / light / medium / heavy), end date, free-text notes
- Form doesn't require anything beyond start date

### 4. Postmenopausal bleeding alert
- If `journey_stage = 'post-menopause'` AND user logs any bleeding → show a clear in-app alert: *"Postmenopausal bleeding should be evaluated by a doctor promptly."*
- This is a guardrail, not a block — user can still log it
- Aligns with medical advice boundary policy: we inform, we don't diagnose

### 5. Journey stage becomes updatable
- Settings page exposes journey stage as an editable field
- System can also auto-update inferred stage based on cycle data:
  - 12 consecutive months without a logged period → infer transition to menopause
  - Surface this as a notification/suggestion, not a silent background update
  - User confirms the inference; it doesn't change without consent

### 6. General settings page (`/settings`)
- **Period tracking:** toggle on/off
- **Journey stage:** view + edit (with confirmation if changing to post-menopause)
- **Account:** email, date of birth (view only or editable TBD)
- Accessible from the main navigation

---

## Feature Scope

### In scope (V1 of this feature)
- `period_logs` table (already designed in DESIGN.md, not yet built)
- `cycle_analysis` table (already designed in DESIGN.md)
- `period_tracking_enabled` preference on user record
- `/period` route — calendar view + log/edit entries
- `/settings` route — general settings page
- Postmenopausal bleeding alert
- Journey stage editable in settings
- Journey stage inference (12 months no period) surfaced as a suggestion
- Retroactive logging (past dates)

### Out of scope (V2+)
- Cycle predictions ("your next period is estimated...")
- PMS pattern analysis
- Contraception-aware cycle modeling
- Push notifications for cycle reminders
- Export of period data (already handled by the general export feature)

---

## Technical Notes

### Database
- `period_logs` table already modeled in DESIGN.md Section 9:
  - `period_start DATE NOT NULL`, `period_end DATE`, `flow_level TEXT`, `notes TEXT`, `cycle_length INTEGER` (calculated)
- `cycle_analysis` table also modeled: avg cycle length, variability (std dev), months since last period, inferred stage
- Need to add `period_tracking_enabled BOOLEAN DEFAULT TRUE` to `users` table (or user settings table)
- `journey_stage` on `users` stays as-is but becomes editable via API

### Backend
- New `period_repository.py` — CRUD for `period_logs` + write `cycle_analysis`
- New `period_service.py` — cycle length calculation, variability, stage inference logic
- Date math (cycle length, streak calculation) → `utils/dates.py`
- Journey stage update via existing `users` route or new endpoint
- Medical alert logic lives in the period service (not the route)

### Frontend
- Calendar component (no existing one — need to evaluate shadcn-svelte calendar or build custom)
- `/period` page with month navigation
- `/settings` page (new navigation item)
- Postmenopausal alert component (reusable, dismissible)

---

## Resolved Questions

1. **`has_uterus` field** — Add it now to settings. If a user indicates they don't have a uterus, period tracking is auto-disabled and hidden.

2. **Calendar component** — Try shadcn-svelte's existing calendar first. Only build custom if it can't support day highlighting and click-to-log.

3. **Journey stage inference consent flow** — Surface as a banner on the `/period` page when 12 months without a logged period is detected. User actively confirms the stage update; system never changes it silently.

4. **Settings navigation** — Settings accessible via a profile/avatar menu in the top-right corner. Keeps main nav clean.

---

## Success Criteria

- A user can log a period start date in under 10 seconds
- A user can view 6 months of period history at a glance on the calendar
- A post-menopause user sees a clear alert when logging any bleeding
- Journey stage can be updated from the settings page
- Period tracking can be disabled, hiding all period-related UI
