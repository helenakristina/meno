# PRD: MHT Medication Tracking

**Feature:** Menopausal Hormone Therapy (MHT) Medication Tracking
**App:** Meno
**Status:** Draft
**Author:** [Your Name]
**Date:** March 18, 2026

---

## Problem Statement

Women on menopausal hormone therapy frequently adjust medications — changing doses, switching delivery methods, trying different formulations — often over months or years. Without a way to track what they took and when, they lose the ability to connect medication changes to symptom improvements or regressions. This makes provider conversations less productive ("I think I switched doses sometime last fall?") and undermines the data-driven self-advocacy that Meno exists to support.

Meno already captures symptom data and period data. Medication tracking is the missing variable that makes the other two meaningfully more powerful.

---

## Goals

1. **Let users record their MHT regimen** — what they take, at what dose, via what delivery method, and when they started or stopped.
2. **Preserve medication history over time** — dose changes, medication switches, and gaps should all be queryable as time windows.
3. **Provide a basic before/after symptom view** — so users can see whether a medication change correlated with symptom pattern shifts.
4. **Integrate medication context into existing features** — Appointment Prep, PDF export, and Ask Meno should all be aware of the user's current and historical medications.
5. **Maintain Meno's optional-feature pattern** — medication tracking is off by default, toggled in settings, and the nav link is hidden when disabled.

### Non-Goals (This PRD)

- Medication reminders or adherence tracking ("did you take your pill today?")
- Non-MHT medication tracking (SSRIs, gabapentin, supplements, etc.)
- Hormone panel / lab value logging
- Full multi-variable correlation dashboard (symptom × period × medication × labs)
- Prescription management or pharmacy integrations

---

## User Stories

1. **As a user starting MHT**, I want to record what my doctor prescribed so I have an accurate record from day one.
2. **As a user changing doses**, I want to end my current regimen entry and start a new one so I can later see how the change affected my symptoms.
3. **As a user whose medication isn't in the reference list**, I want to add it myself so I'm not blocked from tracking.
4. **As a user preparing for an appointment**, I want my current medications included in my appointment prep and export documents so my provider sees the full picture.
5. **As a user wondering "is this working?"**, I want to see my symptom frequency before and after starting a medication so I have data to bring to my provider — not just a feeling.
6. **As a user asking Meno a question**, I want Meno to know what I'm taking so its responses are contextually relevant.

---

## Feature Toggle & Navigation

Medication tracking follows the same optional-feature pattern as period tracking:

- **Default state:** Off
- **Activation:** Settings → Features → "Track MHT Medications" toggle
- **When off:** No "Medications" link in navigation. No medication-related UI anywhere.
- **When on:** "Medications" link appears in navigation. Medication context is injected into Appointment Prep, Export, and Ask Meno.
- **Turning off:** Existing data is preserved (not deleted), but hidden from all features. Turning back on restores it.

---

## Data Model

### `medications_reference` (System-Managed)

Pre-populated reference table of common MHT medications. Users search this when adding a medication. Similar pattern to `symptoms_reference`.

```sql
medications_reference (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_name        TEXT,                     -- e.g., "Climara", "Vivelle-Dot"
  generic_name      TEXT NOT NULL,            -- e.g., "estradiol"
  hormone_type      TEXT NOT NULL CHECK (hormone_type IN (
                      'estrogen', 'progesterone', 'progestin',
                      'testosterone', 'combination'
                    )),
  common_forms      TEXT[],                   -- ['patch', 'pill', 'gel', 'cream', 'ring', 'injection', 'pellet', 'spray']
  common_doses      TEXT[],                   -- ['0.025mg', '0.05mg', '0.075mg', '0.1mg']
  notes             TEXT,                     -- e.g., "Applied twice weekly" or "Bioidentical"
  is_user_created   BOOLEAN DEFAULT FALSE,    -- TRUE for user-added medications
  created_by        UUID REFERENCES users(id),-- NULL for system entries, user_id for user-added
  created_at        TIMESTAMPTZ DEFAULT NOW()
)
```

**RLS policy:** All users can read system entries (`is_user_created = FALSE`). User-created entries are scoped to the creating user only — they do not appear in other users' search/autocomplete results. The creating user can edit/delete their own entries. System entries are read-only.

**Design decision — user-created entries are private:** User-created medications are visible only to the user who created them. This prevents typos from propagating to other users' autocomplete, and — more importantly — prevents user-created medication names from becoming a prompt injection vector, since medication names are injected into LLM context via Ask Meno and Appointment Prep. If a curated "promote to shared" workflow is needed later (e.g., admin review of user-submitted medications), that can be added as a future enhancement.

### `user_medications` (User-Owned, Timeline Model)

Each row represents one medication stint — a specific medication at a specific dose for a specific time window. Dose changes or delivery method changes create a new row (with the previous row's `end_date` set).

```sql
user_medications (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  medication_ref_id UUID REFERENCES medications_reference(id),
  medication_name   TEXT NOT NULL,            -- denormalized for grouping related stints
  dose              TEXT NOT NULL,            -- e.g., "0.05mg", "100mg", "1 pump"
  delivery_method   TEXT NOT NULL CHECK (delivery_method IN (
                      'patch', 'pill', 'gel', 'cream', 'ring',
                      'injection', 'pellet', 'spray', 'troche',
                      'sublingual', 'other'
                    )),
  frequency         TEXT,                     -- e.g., "twice weekly", "daily", "every 3 months"
  start_date        DATE NOT NULL,
  end_date          DATE,                     -- NULL = currently active
  previous_entry_id UUID REFERENCES user_medications(id), -- links dose/delivery changes
  notes             TEXT,                     -- user notes, e.g., "switched because of skin reaction"
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
)
```

**Key design decisions:**

- **`medication_name` (denormalized):** Copied from the reference table at creation time. This field is the grouping key for "show me the history of this medication." It also means the record survives if a user-created reference entry is later deleted.
- **`previous_entry_id`:** Links related stints. When a user changes dose, the UI creates a new row and sets `previous_entry_id` to the old row's ID. This preserves the explicit "this was a change to the same medication" relationship without requiring a separate table. It's optional — a brand new medication has no previous entry.
- **`end_date` NULL = currently active:** Simple, queryable. "What is the user currently taking?" is `WHERE end_date IS NULL`.

**RLS policy:** Standard user isolation. Users can only read/write their own rows.

### Users Table Addition

```sql
-- Added to users table:
-- mht_tracking_enabled  BOOLEAN DEFAULT FALSE
```

---

## Reference Data: Initial Medication Seed

The `medications_reference` table ships pre-populated with the most commonly prescribed MHT medications in the US. This list is curated, not exhaustive — users can add what's missing.

**Estrogen:**

| Brand             | Generic              | Common Forms   | Common Doses                              |
| ----------------- | -------------------- | -------------- | ----------------------------------------- |
| Climara           | estradiol            | patch          | 0.025mg, 0.0375mg, 0.05mg, 0.075mg, 0.1mg |
| Vivelle-Dot       | estradiol            | patch          | 0.025mg, 0.0375mg, 0.05mg, 0.075mg, 0.1mg |
| Estrace           | estradiol            | pill, cream    | 0.5mg, 1mg, 2mg                           |
| Divigel           | estradiol            | gel            | 0.25mg, 0.5mg, 1.0mg                      |
| EstroGel          | estradiol            | gel            | 0.06% (1 pump = 0.75mg)                   |
| Evamist           | estradiol            | spray          | 1.53mg/spray                              |
| Femring           | estradiol acetate    | ring           | 0.05mg/day, 0.1mg/day                     |
| Estring           | estradiol            | ring           | 2mg (releases 7.5mcg/day) — vaginal/local |
| Vagifem / Yuvafem | estradiol            | vaginal tablet | 10mcg                                     |
| Premarin          | conjugated estrogens | pill, cream    | 0.3mg, 0.45mg, 0.625mg, 0.9mg, 1.25mg     |

**Progesterone / Progestins:**

| Brand      | Generic                     | Common Forms        | Common Doses               |
| ---------- | --------------------------- | ------------------- | -------------------------- |
| Prometrium | micronized progesterone     | pill (oral/vaginal) | 100mg, 200mg               |
| Provera    | medroxyprogesterone acetate | pill                | 2.5mg, 5mg, 10mg           |
| Mirena     | levonorgestrel              | IUD                 | 52mg (releases ~20mcg/day) |
| Endometrin | progesterone                | vaginal insert      | 100mg                      |

**Combination:**

| Brand      | Generic                    | Common Forms | Common Doses                                          |
| ---------- | -------------------------- | ------------ | ----------------------------------------------------- |
| Prempro    | conjugated estrogens + MPA | pill         | 0.3mg/1.5mg, 0.45mg/1.5mg, 0.625mg/2.5mg, 0.625mg/5mg |
| Activella  | estradiol + norethindrone  | pill         | 0.5mg/0.1mg, 1mg/0.5mg                                |
| CombiPatch | estradiol + norethindrone  | patch        | 0.05mg/0.14mg, 0.05mg/0.25mg                          |
| Bijuva     | estradiol + progesterone   | pill         | 1mg/100mg                                             |

**Testosterone:**

| Brand                | Generic      | Common Forms       | Common Doses                          |
| -------------------- | ------------ | ------------------ | ------------------------------------- |
| Compounded           | testosterone | cream, gel, pellet | Varies (commonly 0.5-2mg/day topical) |
| AndroGel (off-label) | testosterone | gel                | Varies (titrated to female ranges)    |

_Note: Testosterone for women is commonly compounded rather than brand-name in the US. The reference table should include a "Compounded testosterone" entry with flexible dosing._

---

## User Interface

### Medications Page (Main View)

**Layout:** Card-based, consistent with the rest of Meno.

**Current Medications section (top):**

- One card per active medication (where `end_date IS NULL`)
- Each card shows: medication name, dose, delivery method, frequency, start date, how long active (e.g., "Started 3 months ago")
- Card actions: "Edit" (change dose/method — creates new stint), "Stop" (sets end date), "Notes"

**Past Medications section (below, collapsible):**

- Grouped by `medication_name` (the linking field)
- Shows timeline of stints per medication: dose, delivery method, date range, duration
- Expandable to see notes on each stint

**"Add Medication" flow:**

1. Search/autocomplete against `medications_reference` — shows brand name and generic name
2. If not found: "Add a new medication" link → simple form (generic name, hormone type, common forms, common doses)
3. Select or enter dose
4. Select delivery method (pre-filtered to `common_forms` from reference if available)
5. Enter frequency
6. Set start date (defaults to today)
7. Optional notes
8. Save

**"Change Dose / Method" flow (from active medication card):**

1. User clicks "Edit" on an active medication card
2. Pre-filled form with current values
3. User changes dose, delivery method, and/or frequency
4. "Effective date" field (defaults to today)
5. On save: current stint gets `end_date` = effective date - 1 day, new stint created with `previous_entry_id` linking back
6. User sees updated card immediately

**"Stop Medication" flow:**

1. User clicks "Stop" on an active medication card
2. "When did you stop?" date picker (defaults to today)
3. Optional reason/notes
4. On save: `end_date` set, card moves to Past Medications section

### Settings Integration

Settings → Features section:

- "Track MHT Medications" toggle (same pattern as period tracking toggle)
- When toggled on for the first time: brief explanation of what the feature tracks and a link to the Medications page
- When toggled off: confirmation that data is preserved but hidden

---

## Before/After Symptom Correlation View

This is a basic but powerful view — not a full statistical analysis dashboard, but enough to answer "did things change when I started/changed this medication?"

**Location:** Accessible from each medication card ("See symptom impact") and from the Dashboard.

**How it works:**

1. User selects a medication stint (or the system uses a start date of a medication/dose change).
2. System calculates two time windows of equal length:
   - **Before window:** N days before the start date
   - **After window:** N days after the start date
   - Default N = the length of time the stint has been active, capped at 90 days. User can adjust.
3. For each window, Python/SQL calculates:
   - Top symptom frequencies (count and percentage of days logged)
   - Overall symptom count per day (average)
4. Display as a simple side-by-side comparison — two columns, same symptoms, different numbers.

**What this is NOT:**

- Not a statistical significance test. It does not claim causation.
- Not adjustable for confounders (season, stress, other meds).

**What it IS:**

- A clear, visual way to see "here's what my symptom picture looked like before, and here's what it looks like after."
- Data to bring to a provider conversation: "Since I started estradiol in January, I'm logging hot flashes on 20% of days versus 75% before."

**Display:**

```
Before Estradiol 0.05mg patch          After Estradiol 0.05mg patch
(Oct 1 – Dec 31, 2025)                 (Jan 1 – Mar 18, 2026)
─────────────────────────               ─────────────────────────
Hot flashes: 68 days (74%)             Hot flashes: 18 days (23%)  ↓
Night sweats: 55 days (60%)            Night sweats: 12 days (15%)  ↓
Poor sleep: 71 days (77%)              Poor sleep: 45 days (58%)  ↓
Brain fog: 42 days (46%)               Brain fog: 38 days (49%)  →
Joint pain: 30 days (33%)              Joint pain: 28 days (36%)  →
```

Arrows indicate direction of change. Threshold for showing an arrow: >10 percentage point change.

**Edge cases:**

- Not enough data before the start date: show what's available with a note ("Only 14 days of data available before this medication start")
- No symptom logs in one or both windows: "No symptom data logged during this period"
- Multiple medication changes close together: note that overlapping changes make it harder to attribute shifts to a single medication

**Medical advice boundary:** This view includes a disclaimer: "This comparison shows your logged symptom patterns before and after a medication change. It does not establish that the medication caused any changes. Please discuss your symptom patterns and treatment with your healthcare provider."

---

## Integration with Existing Features

### Appointment Prep (Step 2 — Surface the Data Story)

When medication tracking is enabled:

- The LLM-generated narrative summary includes medication context: "During this period, you were taking [medication] at [dose]. You started [medication] on [date], which falls within the analysis window."
- If a medication change occurred during the analysis window, the narrative calls this out as a potentially significant data point.
- The scenario cards (Step 4) can reference medication context: "If your provider suggests changing your dose..."

**Data sent to LLM (anonymized, per existing policy):**

- Current medications: name, dose, delivery method, duration
- Any medication changes in the analysis window: what changed, when
- No prescribing provider names, no notes

### PDF Export

When medication tracking is enabled, the Doctor Visit Summary PDF includes a new section:

**"Current Medications" section (after Patient Context, before Symptom Patterns):**

- List of active medications: name, dose, delivery method, frequency, start date
- Any medication changes during the export date range: what changed, when, previous dose/method

This is factual data only — no AI-generated commentary on medication effectiveness.

### Ask Meno

When medication tracking is enabled, the user context injected per query (assembled in FastAPI) adds:

- Current medications: name, dose, delivery method, how long active
- Recent medication changes (last 90 days): what changed, when

This allows Ask Meno to give contextually relevant responses. Example: if a user asks "why am I getting headaches?" and they recently started a new estrogen formulation, Ask Meno can surface research about headaches as a common initial side effect of estrogen therapy — grounded in RAG sources, not speculation.

**Ask Meno does NOT:**

- Evaluate whether the user's medication or dose is appropriate
- Suggest medication changes
- Interpret symptom changes as medication effects

**Ask Meno CAN:**

- Share what research says about common side effects of the user's medication type
- Note that the user recently changed medications when discussing new symptom patterns
- Suggest questions to ask a provider about their specific medication

---

## Patch Replacement & Placement Tracking (Decision Required)

This section presents two options for the planning phase. Patch-based delivery is one of the most common MHT methods, and tracking replacement schedules and placement rotation is a real user need — but it adds meaningful complexity.

### Option A: Cut for V1, Capture for Later

**What ships:** The medication record captures that the delivery method is "patch" and the frequency is "twice weekly" (or whatever the schedule is). No reminders, no placement tracking.

**Future enhancement:** A separate, lightweight PRD for patch management that includes date-based replacement reminders, placement rotation tracking (to avoid skin irritation), and optional push notifications.

**Tradeoff:** Simpler scope, faster to ship. Users who need patch reminders continue using their phone alarms or calendar events (which most already do).

### Option B: Simple Optional Reminder

**What ships:** When a user's delivery method is "patch," they see an additional optional section on their medication card:

- "Remind me to change my patch" toggle
- Frequency: pulled from the medication's `frequency` field (e.g., "twice weekly")
- Last changed date: user-entered, defaults to start date
- Next change due: calculated from last changed + frequency
- Visual indicator on the medication card: "Change due today" / "Change due in 2 days" / "Overdue by 1 day"

**No push notifications in this version** — just a visible status on the Medications page and optionally on the Dashboard.

**No placement tracking in this version** — that's a more complex UX (body diagram, rotation suggestions) better suited for its own iteration.

**Tradeoff:** Adds a small amount of additional data modeling (`last_patch_change DATE`, `reminder_enabled BOOLEAN` on `user_medications`) and UI work, but stays within reasonable scope. Useful enough to be worth it if the team bandwidth allows.

**Data model addition for Option B:**

```sql
-- Added to user_medications (only relevant when delivery_method = 'patch'):
-- patch_reminder_enabled   BOOLEAN DEFAULT FALSE
-- last_patch_change        DATE
-- patch_change_frequency_days  INTEGER  -- calculated from frequency, e.g., 3 for "twice weekly"
```

---

## Technical Implementation Notes

### Division of Labor (Consistent with Existing Patterns)

| Task                                                                | Who Does It            | Why                      |
| ------------------------------------------------------------------- | ---------------------- | ------------------------ |
| Store/retrieve medication records                                   | Python/SQL             | CRUD, deterministic      |
| Calculate before/after symptom frequencies                          | Python/SQL             | Deterministic, exact     |
| Determine time windows for comparison                               | Python/SQL             | Date math, deterministic |
| Search/autocomplete medications_reference                           | SQL (ILIKE or trigram) | Fast, simple             |
| Write narrative incorporating medication context (Appointment Prep) | LLM                    | Meaning-making, nuance   |
| Answer medication-related educational questions (Ask Meno)          | LLM + RAG              | Grounded reasoning       |
| Generate suggested provider questions about medications             | LLM + RAG              | Personalized reasoning   |

### API Endpoints (FastAPI)

- `GET /medications/reference?search={query}` — search reference table
- `POST /medications/reference` — add user-created medication to reference
- `GET /medications` — list user's medications (active and past)
- `POST /medications` — add a new medication stint
- `PUT /medications/{id}` — update a stint (primarily for setting end_date)
- `POST /medications/{id}/change` — create a new stint from an existing one (dose/method change), automatically ending the previous stint
- `GET /medications/{id}/symptom-comparison` — before/after symptom data for a specific stint
- `GET /medications/current` — just active medications (for injection into other features)

### Frontend Routes (SvelteKit)

- `/medications` — main medications page (gated by feature toggle)
- `/medications/add` — add medication flow
- `/medications/{id}` — medication detail / history view
- `/medications/{id}/impact` — before/after symptom comparison

### Symptom Summary Cache

The existing `symptom_summary_cache` should be invalidated and regenerated when:

- A medication is added, changed, or stopped (the cache text should mention current medications when the feature is enabled)

---

## Privacy & Ethics

All existing Meno privacy principles apply without modification:

- **Anonymization before LLM:** Medication names and doses are sent to the LLM, but no user identifiers, provider names, or dates of birth. Consistent with existing policy.
- **RLS isolation:** `user_medications` rows are user-scoped via Row Level Security. Users cannot see each other's medication data.
- **`medications_reference` — user entries are private:** User-created reference entries are scoped to the creating user via RLS. This prevents typos from polluting other users' search results and — critically — prevents user-created medication names from becoming a prompt injection vector when injected into LLM context. System-seeded entries are readable by all users.
- **No medication recommendations:** Meno tracks what the user tells it. It does not suggest medications, doses, or changes. The before/after view shows patterns, not prescriptions.
- **Export includes meds only when enabled:** If the user has medication tracking off, exports and appointment prep behave exactly as they do today.

---

## Success Metrics

- **Adoption:** % of active users who enable medication tracking within 30 days of feature launch
- **Completeness:** % of medication entries that include all fields (dose, delivery method, frequency, start date)
- **Engagement with correlation view:** % of medication-tracking users who view the before/after symptom comparison at least once
- **Integration usage:** % of exports and appointment prep sessions that include medication context (among users with tracking enabled)

---

## Future Enhancements (Out of Scope, Captured for Reference)

- **Patch replacement reminders with push notifications** (if Option A is chosen above, or as an extension of Option B)
- **Patch placement rotation tracking** — body diagram UI, rotation suggestions to prevent skin irritation
- **Non-MHT medication tracking** — SSRIs, gabapentin, supplements commonly used in menopause management
- **Hormone panel / lab value logging** — track bloodwork results over time
- **Full multi-variable correlation dashboard** — symptom × period × medication × labs, with trend lines and statistical analysis
- **Medication interaction awareness** — surface known interactions between tracked medications (would require a drug interaction database)
- **Compounding pharmacy integration** — for users on compounded hormones, capture the specific formulation details
- **Adherence tracking** — "did you take your medication today?" daily check-in (deliberately excluded from V1 to avoid Meno feeling like a nag)

---

## Open Questions

1. **How many days of data constitute "enough" for a meaningful before/after comparison?** The current design shows whatever is available with a note when data is sparse. Should there be a minimum (e.g., 14 days) below which the comparison isn't offered at all?
2. **Should the before/after view account for a "ramp-up" period?** Many MHT medications take 2-4 weeks to reach full effect. Should the after window exclude the first N days? Or is that overcomplicating the first pass?
3. **Reference table maintenance:** Who updates the system seed data as new medications come to market? Manual process for now, but worth thinking about.
4. **Promoting user-created medications to shared?** If a user-created medication turns out to be a real, commonly-used formulation, should there be an admin workflow to review and promote it to a system entry? Low priority but worth noting.
