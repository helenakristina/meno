# Brainstorm: MHT Medication Tracking

**Date:** 2026-03-18
**Status:** Decisions locked — ready for planning
**PRD Source:** `docs/planning/PRD_MED_TRACKING.md`

---

## What We're Building

A medication tracking feature for users on Menopausal Hormone Therapy (MHT). Users can record what they're taking, at what dose, via what delivery method, and when they started or changed. The feature also includes a before/after symptom comparison view that lets users see how their symptom patterns shifted around a medication change — data they can bring to provider conversations.

Medication tracking is off by default, toggled in Settings, following the same optional-feature pattern as period tracking.

---

## Why This Approach

The PRD was thorough and arrived with a clear data model, UI flows, API design, and integration plan. Brainstorming focused on resolving the four open questions, not re-examining the core approach.

The timeline model for `user_medications` (each row = one stint, new row on dose change, `end_date NULL` = currently active) is well-suited to the query patterns this feature needs: "what is the user currently taking?" and "what were they taking on date X?" It mirrors how providers think about medication history.

---

## Key Decisions

### 1. Patch reminders: Skip for V1 (Option A)

The core medication tracking feature is already substantial (2 new tables, 8 endpoints, 4 routes, before/after comparison, 3 feature integrations). Adding patch replacement reminders adds conditional UI, date calculation logic, and 3 new schema fields for modest incremental value — users already handle this with phone alarms.

**What ships:** Patches are recorded as a delivery method with frequency noted. No visual reminder, no "next change due" calculation.

**Captured for later:** Option B (simple visual reminder) and Option C (push notifications + placement rotation) documented in PRD Future Enhancements.

### 2. Before/after comparison: Always show, note sparse data

No minimum day threshold before offering the comparison view. Reasons:
- Users with short "before" windows aren't at fault — they may have just started using Meno before starting a medication
- Some MHT effects are rapid (hot flashes can change within hours of starting estrogen) — gating the view on 14 days would hide exactly this kind of early signal
- The comparison is framed as "data to bring to your provider," not a statistical study — sparse data with a clear note is more honest than a hard gate

**Implementation:** When either window has fewer than 14 days of symptom logs, show the data with a visible note (e.g., "Only 8 days of data available before this medication — more data will make this comparison more meaningful").

### 3. Ramp-up exclusion: Skip

The after window starts from day 1 of the medication, not day 14. Reasons:
- Some effects appear very quickly; a 14-day exclusion would hide fast-acting responses
- The before/after view is not a clinical measurement — the disclaimer already covers the "correlation ≠ causation" nuance
- Excluding the first 14 days creates a confusing UX ("why does my after window start 2 weeks after I started?")
- MHT ramp-up varies by person and formulation — 14 days is a rough rule of thumb, not a clean clinical cutoff

---

## Resolved Open Questions

| Question | Decision |
|---|---|
| Minimum days for before/after? | No minimum — always show, note sparse data |
| Ramp-up exclusion period? | None — after window starts day 1 |
| Patch replacement tracking? | Option A — skip for V1 |
| Reference table maintenance? | Manual process for now — noted as future consideration |
| Promoting user-created meds to shared? | Admin workflow deferred — low priority |

---

## Scope Summary

**In scope for V1:**
- `medications_reference` table with system seed data (estrogen, progesterone, combination, testosterone)
- `user_medications` table (timeline model, `previous_entry_id` chaining)
- `mht_tracking_enabled` boolean on users table
- Feature toggle in Settings (same pattern as period tracking)
- Medications page: current meds + past meds (collapsible, grouped by medication name)
- Add medication flow (search/autocomplete, add-your-own fallback)
- Change dose/method flow (creates new stint, ends previous)
- Stop medication flow (sets end_date)
- Before/after symptom comparison view (Python calculates, always show, note sparse data)
- Integration: Appointment Prep narrative + scenario cards
- Integration: PDF export (Current Medications section)
- Integration: Ask Meno context injection (current meds + recent changes)
- `symptom_summary_cache` invalidation on medication add/change/stop

**Explicitly out of scope for V1:**
- Patch replacement reminders
- Non-MHT medication tracking
- Hormone panel / lab value logging
- Multi-variable correlation dashboard
- Medication reminders / adherence tracking

---

## Architecture Notes

Follows existing Meno patterns throughout:

- **Backend:** Models → Repositories → Services → Dependencies → Routes (standard build order)
- **Division of labor:** Python/SQL for all date math, frequency calculations, and before/after statistics. LLM for narrative generation incorporating medication context.
- **User-created medication entries are private:** RLS ensures user-created `medications_reference` entries are only visible to the creating user — prevents typo propagation and LLM prompt injection via user-controlled medication names
- **Anonymization before LLM:** Medication names and doses passed to LLM; no user identifiers, provider names, or DOB
- **Medical advice boundary:** Before/after view includes disclaimer; Ask Meno can share research about medication types but cannot evaluate appropriateness or suggest changes
