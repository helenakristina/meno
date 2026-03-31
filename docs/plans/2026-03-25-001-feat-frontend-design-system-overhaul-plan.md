---
title: "feat: Frontend Design System Overhaul"
type: feat
status: completed
date: 2026-03-25
---

# ✨ Frontend Design System Overhaul

## Overview

Apply the Meno `frontend-design` skill tokens uniformly across every frontend page and component. Replace all ad-hoc `slate-*`, `teal-*`, and off-palette colors with the canonical `neutral-*`, `primary-*`, `accent-*`, and semantic token classes. Add the Meno logo to the navigation bar. The result is an app that looks like a single designer built every screen.

The design tokens themselves have already been added to `layout.css`'s `@theme inline` block (committed 2026-03-25). This plan covers everything downstream of that foundation.

---

## Problem Statement

The Meno frontend has accumulated styling drift across months of parallel feature development:

- **Two neutral scales in use:** `slate-*` (Tailwind's cool gray, 117+ occurrences) and `neutral-*` (warm gray, 0 occurrences in components). The design skill specifies warm neutral. Every page uses the wrong palette.
- **shadcn `--primary` CSS variable unpatched:** Still maps to the default near-navy blue (`oklch(0.208 0.042 265.755)`). Any `<Button>` component that uses the default `bg-primary` variant renders dark navy, not teal. This is a silent visual bug.
- **Dark backgrounds on interactive elements (Rule 2 violation):** `bg-slate-900` (dashboard CTA), `bg-slate-800` (settings save, profile avatar). The design skill explicitly forbids these.
- **Active nav state:** Uses `bg-slate-100 text-slate-900` — no teal. Should be `text-primary-600 font-semibold`.
- **Off-palette badges:** `to_call` shortlist status uses `bg-blue-100 text-blue-700`. Blue is not in the Meno palette.
- **Semantic token bypass:** Success states use `emerald-*`, warnings use raw `amber-*`, danger uses `red-*` directly rather than the defined semantic tokens.

---

## Proposed Solution

Work through the codebase in a specific order that minimizes regression risk: fix the root CSS variable first, update the layout/nav, then proceed page by page. Each change is a color-class substitution — no layout restructuring, no functionality changes.

### Color Migration Reference

This table is the authoritative mapping for the entire overhaul:

| Old class            | New class              | Notes                                  |
| -------------------- | ---------------------- | -------------------------------------- |
| `bg-slate-50`        | `bg-neutral-50`        | Page backgrounds, subtle fills         |
| `bg-slate-100`       | `bg-neutral-100`       | Hover backgrounds, skeleton            |
| `bg-slate-200`       | `bg-neutral-200`       | Skeleton loaders                       |
| `bg-slate-300`       | `bg-neutral-300`       | Disabled                               |
| `bg-slate-400`       | `bg-neutral-400`       | —                                      |
| `bg-slate-800`       | `bg-primary-600`       | **Rule 2 violation** — dark bg buttons |
| `bg-slate-900`       | `bg-primary-500`       | **Rule 2 violation** — dark bg CTA     |
| `text-slate-400`     | `text-neutral-400`     | Secondary/muted text                   |
| `text-slate-500`     | `text-neutral-500`     | Muted body                             |
| `text-slate-600`     | `text-neutral-600`     | Body text                              |
| `text-slate-700`     | `text-neutral-700`     | Strong body                            |
| `text-slate-800`     | `text-neutral-800`     | Headings                               |
| `text-slate-900`     | `text-neutral-900`     | High-contrast (use sparingly)          |
| `border-slate-100`   | `border-neutral-100`   | —                                      |
| `border-slate-200`   | `border-neutral-200`   | Cards, inputs, nav                     |
| `border-slate-300`   | `border-neutral-300`   | Input borders                          |
| `bg-teal-50`         | `bg-primary-50`        | Hover/selected tints                   |
| `bg-teal-100`        | `bg-primary-100`       | Selected chips                         |
| `bg-teal-400`        | `bg-primary-400`       | Secondary elements                     |
| `bg-teal-500`        | `bg-primary-500`       | Progress bars, chart fills             |
| `bg-teal-600`        | `bg-primary-500`       | Primary buttons (use 500, not 600)     |
| `bg-teal-700`        | `bg-primary-600`       | Button hover states                    |
| `text-teal-600`      | `text-primary-600`     | Links, active nav                      |
| `text-teal-700`      | `text-primary-700`     | Pressed/hover text                     |
| `text-teal-800`      | `text-primary-800`     | Dark badge text on light teal          |
| `border-teal-100`    | `border-primary-100`   | —                                      |
| `border-teal-300`    | `border-primary-300`   | Hover borders                          |
| `border-teal-400`    | `border-primary-400`   | Focus states                           |
| `ring-teal-200`      | `ring-primary-200`     | —                                      |
| `ring-teal-300`      | `ring-primary-300`     | Focus rings                            |
| `ring-teal-400`      | `ring-primary-400`     | —                                      |
| `ring-teal-500`      | `ring-primary-500`     | Focus rings                            |
| `ring-slate-200`     | `ring-neutral-200`     | —                                      |
| `ring-slate-500`     | `ring-primary-500`     | **Form inputs — wrong ring color**     |
| `bg-emerald-50`      | `bg-success-light`     | Success state backgrounds              |
| `border-emerald-200` | `border-success-light` | —                                      |
| `text-emerald-700`   | `text-success`         | Success text                           |
| `text-emerald-800`   | `text-success-dark`    | —                                      |
| `bg-green-100`       | `bg-primary-100`       | Provider booking badge                 |
| `text-green-700`     | `text-primary-800`     | Provider booking badge text            |
| `bg-blue-100`        | `bg-accent-100`        | Provider `to_call` badge               |
| `text-blue-700`      | `text-accent-800`      | Provider `to_call` badge text          |
| `bg-amber-50`        | `bg-warning-light`     | Medical disclaimer, NAMS badge         |
| `bg-amber-100`       | `bg-warning-light`     | Warning tints                          |
| `border-amber-200`   | `border-warning`       | Warning borders                        |
| `text-amber-700`     | `text-warning-dark`    | Warning text                           |
| `text-amber-800`     | `text-warning-dark`    | —                                      |

> **Period calendar (rose-\*):** The design skill specifies accent coral for period indicators. The current implementation uses `rose-*` (pink-red family), which is arguably a better UX choice for menstrual flow. **This is a decision point** — see Phase 3e below. Recommend leaving `rose-*` for flow levels but using `accent-*` for non-flow period UI elements (log buttons, calendar header accents).

---

## Technical Approach

### Phase 0: Unblock `<Button>` — Fix shadcn `--primary` variable (Critical)

**File:** `frontend/src/routes/layout.css`

The `--primary` CSS variable in the `:root` block currently maps to `oklch(0.208 0.042 265.755)` (near-navy). Every use of shadcn's `<Button>` component (default variant = `bg-primary`) renders dark navy. This must be fixed first.

**Change:** In the `:root` block, update `--primary` to the Meno teal:

```css
/* Before */
--primary: oklch(0.208 0.042 265.755);
--primary-foreground: oklch(0.984 0.003 247.858);

/* After */
--primary: oklch(0.65 0.15 175); /* ≈ #14b892 teal */
--primary-foreground: oklch(1 0 0); /* white */
```

Also update the `.dark` block's `--primary` to an appropriate teal-based value for dark mode consistency.

> **Note:** The exact oklch conversion of `#14b892` is approximately `oklch(0.65 0.147 175)`. Verify visually after applying.

### Phase 1: Navigation Bar

**File:** `frontend/src/routes/(app)/+layout.svelte`

Changes:

- Add `<img src={logo} alt="Meno" class="h-8 w-auto" />` to the wordmark area. Import logo: `import logo from '$lib/assets/logo.png'`
- Wordmark text: `text-slate-900` → `text-neutral-800`
- Inactive nav links: `text-slate-700 hover:bg-slate-100 hover:text-slate-900` → `text-neutral-600 hover:text-primary-600`
- Active nav link: `bg-slate-100 text-slate-900` → `text-primary-600 font-semibold border-b-2 border-primary-500` (remove `bg-slate-100`)
- Profile avatar button: `bg-slate-800 text-white hover:bg-slate-700` → `bg-primary-500 text-white hover:bg-primary-600`
- Page wrapper background: `bg-slate-50` → `bg-neutral-50`
- Mobile sidebar: apply the same mapping

### Phase 2: Auth pages

**Files:** `login/+page.svelte`, `onboarding/+page.svelte`

- All `text-slate-*` → `text-neutral-*`
- Input focus: `focus:border-slate-500 focus:ring-1 focus:ring-slate-500` → `focus:border-primary-500 focus:ring-1 focus:ring-primary-500`
- Button colors: any dark/slate buttons → teal
- `border-slate-*` → `border-neutral-*`

### Phase 3: App pages (in order)

Work through each page applying the color migration table. Key items per page:

#### 3a. Dashboard (`dashboard/+page.svelte`)

- "Log today's symptoms" CTA button: `bg-slate-900 text-white hover:bg-slate-800` → `bg-primary-500 text-white hover:bg-primary-600` (Rule 2 violation — highest priority)
- All `text-slate-*` → `text-neutral-*`
- Chart bar fills: already use `teal-*` → migrate to `primary-*`
- Empty state text and borders: slate → neutral

#### 3b. Log Symptoms (`log/+page.svelte`)

- All `text-slate-*` and `border-slate-*` → neutral equivalents
- Success state: `border-emerald-200 bg-emerald-50` → `border-success-light bg-success-light`; `text-emerald-*` → `text-success-*`
- Symptom card dismiss button: `hover:bg-red-50 hover:text-red-500` → `hover:bg-neutral-100 hover:text-neutral-600` (Rule 8 — red is for destructive only)
- Selected symptom cards: `teal-*` → `primary-*`
- Submit button: `teal-*` → `primary-*`

#### 3c. Ask Meno (`ask/+page.svelte`, `ask/history/+page.svelte`)

- Medical disclaimer banner: verify it uses `warning-*` tokens (if using raw `amber-*`, migrate)
- User chat bubble: `bg-slate-700` → `bg-primary-600` (dark background on interactive area)
- All `text-slate-*` → `text-neutral-*`
- Input focus rings: slate → primary

#### 3d. Appointment Prep (`appointment-prep/+page.svelte`, Step1Context.svelte–Step5Generate.svelte)

- Each step component: full slate → neutral sweep
- Action buttons: verify teal classes → migrate to primary tokens
- Any `bg-slate-800/900` buttons → teal

#### 3e. Providers (`providers/+page.svelte`, `ProviderCard.svelte`, `ProviderFilters.svelte`, `CallingScriptModal.svelte`)

Specific badge fixes in `providers/+page.svelte` STATUS_CONFIG:

```javascript
// Before
to_call: {
  badge: "bg-blue-100 text-blue-700";
}
booking: {
  badge: "bg-green-100 text-green-700";
}

// After
to_call: {
  badge: "bg-accent-100 text-accent-800";
}
booking: {
  badge: "bg-primary-100 text-primary-800";
}
```

In `ProviderCard.svelte`:

- NAMS certification badge: `bg-amber-50 border-amber-200 text-amber-700` → `bg-primary-50 border-primary-200 text-primary-700` (amber is warning-only per the skill; a certification badge should use primary teal)
- Provider type badge: `teal-*` → `primary-*`
- Insurance tags: `border-slate-200 bg-slate-50 text-slate-600` → neutral equivalents

#### 3f. Period tracking (`period/+page.svelte`, `PeriodCalendar.svelte`, `PeriodLogModal.svelte`)

**Decision point on flow colors:** `rose-*` is currently used for flow levels (spotting → heavy). The design skill says to use accent coral for period indicators. However, `rose` (pink-red) is more intuitive for menstrual flow than coral/orange.

**Recommendation:** Keep `rose-*` for the flow level visualization inside the calendar cells. Use `accent-*` (coral) for non-flow period UI: the "Log period" button, the period tracking section header, and any period-related badges or chips. This splits the difference between design skill compliance and UX clarity.

"Log period" button: must use `bg-primary-500` (teal), not red/rose — this is explicitly called out in the PRD.

All `text-slate-*`, `border-slate-*` → neutral equivalents.

#### 3g. Medications (`medications/+page.svelte`, `add/`, `[id]/`, `[id]/impact/`)

In `[id]/impact/+page.svelte` — medication impact table:

- Positive change (decrease): `text-success` ✅ (verify — may already be correct)
- Negative change (increase): `text-danger` ✅ (verify)
- Neutral: `text-neutral-500`

All form inputs on add/edit pages: migrate focus rings slate → primary.
All `text-slate-*` → `text-neutral-*`.

#### 3h. Export, Settings (`export/+page.svelte`, `settings/+page.svelte`)

Settings save buttons: `bg-slate-800 text-white hover:bg-slate-700` → `bg-primary-500 text-white hover:bg-primary-600` (Rule 2 violation).

Full slate → neutral sweep on both pages.

---

## System-Wide Impact

### Interaction Graph

This is a pure CSS class substitution. No JavaScript logic, event handlers, or state changes. The only cascading effect is:

- `layout.css` `--primary` override → changes the rendered color of all shadcn `<Button>` components globally (all pages simultaneously)
- Nav changes in `(app)/+layout.svelte` → affects every app page simultaneously

### Error & Failure Propagation

No runtime errors expected from color class changes. The only risk is:

- `bg-primary-*` class not found → Tailwind won't generate it → element renders with no background. This would happen if the `@theme inline` block has a typo in the token name. Visual regression only, no JS errors.
- `--primary` oklch value: if the oklch conversion is slightly off, the rendered color will be close but not pixel-perfect. Verify visually.

### State Lifecycle Risks

None — no state, no persistence, no data changes.

### API Surface Parity

None — backend unchanged.

### Integration Test Scenarios

Since this is visual-only, "integration testing" = manual visual review:

1. **Submit a form** after updating input focus colors — confirm focus ring is teal, not slate
2. **Delete an appointment** after updating button colors — confirm the danger button is still red (not accidentally overwritten)
3. **Navigate between pages** — confirm active nav state shows teal underline/text, not gray
4. **View a provider shortlist** — confirm all badge variants render correctly with new colors
5. **Open a modal/dialog** — confirm modal overlay and button colors are correct inside the modal context

---

## Acceptance Criteria

### Visual

- [ ] Logo appears in the navigation bar at 32px height, maintaining aspect ratio
- [ ] Favicon appears in browser tab (already added — verify it shows)
- [ ] All primary action buttons use `primary-500` teal (no navy, no slate-800/900)
- [ ] Active nav item shows `text-primary-600` with bottom border indicator
- [ ] Profile avatar button is teal, not dark slate
- [ ] All links are `text-primary-600 hover:text-primary-700` — consistent across all pages
- [ ] All cards follow `bg-white border border-neutral-200 rounded-lg p-6`
- [ ] Provider badges: `to_call` = coral, `booking` = teal, `left_voicemail` = warning-yellow
- [ ] Dashboard chart bars use `primary-400/500` teal
- [ ] "Log period" button is teal, not red/rose
- [ ] Text uses warm neutral palette — no cool slate grays
- [ ] Medical disclaimer banner uses warning semantic colors
- [ ] Success states use `success-*` semantic tokens
- [ ] Form focus rings are `primary-500` teal throughout
- [ ] No off-palette colors anywhere (no navy, blue-100 badges, violet-50, or random emerald)
- [ ] The app feels visually cohesive — one designer, one palette

### Functional (no regressions)

- [ ] All buttons still work (click → correct action fires)
- [ ] All forms still submit
- [ ] All nav links still navigate correctly
- [ ] Delete/destructive actions: danger red still renders correctly
- [ ] Period calendar: flow level colors still render (whether rose or accent)
- [ ] Medication impact table: green/red still render for positive/negative changes

---

## Implementation Order (Summary)

```
Phase 0  layout.css            Fix --primary CSS variable (unblocks <Button>)
Phase 1  (app)/+layout.svelte  Logo + nav colors
Phase 2  login, onboarding     Auth pages
Phase 3a dashboard             CTA button (Rule 2 priority)
Phase 3b log                   Dismiss button, success state
Phase 3c ask, ask/history      Chat bubble, disclaimer
Phase 3d appointment-prep      5 step files + orchestrator
Phase 3e providers             Badge fixes, ProviderCard
Phase 3f period                Log button, calendar decision
Phase 3g medications           4 pages, impact table
Phase 3h export, settings      Save buttons
```

---

## Alternative Approaches Considered

**Option A: Create a Button.svelte wrapper instead of fixing shadcn `--primary`**
Rejected — adds a component layer for a problem that is correctly solved at the CSS variable level. Fixing the root variable is the right approach.

**Option B: Replace `slate-*` with `gray-*` (Tailwind's warm gray) as a transitional step**
Rejected — `neutral-*` in Tailwind 4 maps to the design skill tokens we've already defined. Going directly to `neutral-*` is correct.

**Option C: Update the shadcn color system to use `@layer components` overrides**
Rejected — unnecessary complexity. A CSS variable override in `:root` is idiomatic for shadcn.

---

## Decision Points

1. **`--primary` oklch value:** The design skill specifies `#14b892`. The oklch conversion is approximately `oklch(0.65 0.147 175)`. Verify the rendered color visually against the design spec — adjust if needed.

2. **Period flow colors (rose vs. accent coral):** Recommendation is to keep `rose-*` for calendar cell flow level fills, use `accent-*` for period-related UI elements outside the calendar. Confirm with Helena before implementing. I want you to use the accent color, NOT ROSE for the menstrual flow. Just because blood is red does not mean heavy days need to be dark red. It is intuitive using the coral accent colors and they go with our app.

3. **NAMS badge:** Design skill has no certification/prestige badge color. Current implementation uses amber (warning-only). Recommendation: `primary-50/200/700` teal. Confirm acceptable. Yes, that is acceptable.

---

## Testing

Visual-only overhaul — no unit tests needed or expected. Manual review process:

1. Run `npm run dev` in `frontend/`
2. Walk every page in order (dashboard → log → ask → appointment-prep → providers → period → medications → export → settings)
3. Check each page against the acceptance criteria above
4. Test auth flow: login, onboarding
5. Test modal/dialog interactions on providers and appointment-prep pages
6. Verify no console errors

---

## Sources & References

### Internal

- **PRD:** `docs/planning/prds/PRD_FRONTEND_OVERHAUL.md`
- **Design skill:** `.claude/skills/frontend-design/SKILL.md` — authoritative source for all colors and patterns
- **Design tokens (already in place):** `frontend/src/routes/layout.css` — `@theme inline` block (committed 2026-03-25)
- **Nav bar code:** `frontend/src/routes/(app)/+layout.svelte`
- **Providers badge config:** `frontend/src/routes/(app)/providers/+page.svelte:94`
- **Button component:** `frontend/src/lib/components/ui/button/button.svelte`
- **ProviderCard badges:** `frontend/src/lib/components/providers/ProviderCard.svelte`

### Institutional Learnings (from `docs/solutions/`)

- **Svelte 5 `$derived` vs `$derived.by()`** — if any styling logic is reactive, use `$derived.by()` not `$derived(() => {})`. See `docs/solutions/ui-bugs/svelte5-derived-thunk-and-bits-ui-calendar-key-collision.md`.
- **No JavaScript changes expected** — this overhaul is class substitutions only. The learnings around `$derived`, combobox event ordering, and type mismatches are not in scope here.
