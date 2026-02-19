# Dashboard — Developer Documentation

**Route:** `/dashboard`
**File:** `frontend/src/routes/(app)/dashboard/+page.svelte`
**Phase:** V1
**Last Updated:** February 2026

---

## Overview

The dashboard is the home view for authenticated users. It contains two independent sections that share a global date-range filter:

1. **Most Frequent Symptoms** — horizontal bar chart of the top 10 symptoms logged in the selected period, powered by `GET /api/symptoms/stats/frequency`
2. **Symptom History** — chronological log entries grouped by day, powered by `GET /api/symptoms/logs`

Both sections fetch in parallel on mount and whenever the date range changes. Each section has its own loading, error, and empty states, so a failure in one does not affect the other.

The page lives inside the `(app)` layout group which handles authentication guard and navigation. No `+page.server.ts` or `+page.ts` load function is used — all data fetching happens reactively via `$effect`.

---

## Related Documentation

- **Frequency stats API:** [`docs/dev/backend/symptom-stats-api.md`](../backend/symptom-stats-api.md)
- **Symptom logs API:** [`docs/dev/backend/symptom-logging-api.md`](../backend/symptom-logging-api.md)
- **Data models:** [`docs/dev/DESIGN.md §9`](../DESIGN.md#9-data-models)
- **UX specification:** [`docs/dev/DESIGN.md §10.3`](../DESIGN.md#103-dashboard)
- **User guide:** [`docs/user/how-to-dashboard.md`](../../user/how-to-dashboard.md)

---

## State Model

All state is managed with Svelte 5 runes (`$state`, `$derived`). There is no external store; state is local to the component and resets on navigation.

### Reactive State (`$state`)

| Variable | Type | Initial | Description |
|---|---|---|---|
| `loading` | `boolean` | `true` | History section: true while fetch is in-flight |
| `error` | `string` | `''` | History section: error message; empty = no error shown |
| `logs` | `Log[]` | `[]` | Raw log array from `/api/symptoms/logs` |
| `frequencyLoading` | `boolean` | `true` | Chart section: true while fetch is in-flight |
| `frequencyError` | `string` | `''` | Chart section: error message; empty = no error shown |
| `frequencyStats` | `SymptomFrequency[]` | `[]` | Raw frequency data from `/api/symptoms/stats/frequency` |
| `selectedRange` | `string` | `'7'` | Active date range: `'7'`, `'14'`, or `'30'` |
| `expandedNotes` | `Record<string, boolean>` | `{}` | Maps YYYY-MM-DD date keys to notes-expanded state |

### Derived State (`$derived`)

| Variable | Type | Logic |
|---|---|---|
| `dayGroups` | `DayGroup[]` | `groupByDay(logs)` — groups logs by local date, deduplicates symptoms, extracts free-text entries |
| `topSymptoms` | `SymptomFrequency[]` | `frequencyStats.slice(0, 10)` — caps chart at 10 bars |
| `maxCount` | `number` | `topSymptoms[0]?.count ?? 1` — denominator for bar widths; `?? 1` prevents division by zero |

---

## Data Flow

### Reactive Trigger

```
selectedRange changes (user picks dropdown)
  └─ $effect → fetchAll(selectedRange)
```

The `$effect` also fires on mount (initial render with `selectedRange = '7'`).

### fetchAll — Parallel Fetch Strategy

```
fetchAll(range)
  ├─ Set loading = true, frequencyLoading = true
  ├─ supabase.auth.getSession() → get JWT access_token
  ├─ If no token → set both error states, return early
  ├─ Calculate startDateStr (en-CA locale, YYYY-MM-DD)
  └─ Promise.all([
       fetchLogs(token, startDateStr),
       fetchFrequencyStats(token, startDateStr)
     ])
```

Token is fetched once and shared across both calls, saving one round-trip per range change.

### Start Date Calculation

```typescript
const startDate = new Date();
startDate.setDate(startDate.getDate() - (parseInt(range) - 1));
const startDateStr = startDate.toLocaleDateString('en-CA');
```

| `selectedRange` | Days subtracted | Effective window |
|---|---|---|
| `'7'` | 6 | Today + 6 prior days |
| `'14'` | 13 | Today + 13 prior days |
| `'30'` | 29 | Today + 29 prior days |

`en-CA` locale produces `YYYY-MM-DD` reliably across all browsers.

### fetchLogs

```
GET /api/symptoms/logs?start_date={startDateStr}&limit=100
Authorization: Bearer {token}
  ├─ ok    → logs = data.logs ?? []
  ├─ !ok   → error = "Failed to load your history ({status})…"
  └─ throw → error = "Network error…"
  finally  → loading = false
```

### fetchFrequencyStats

```
GET /api/symptoms/stats/frequency?start_date={startDateStr}
Authorization: Bearer {token}
  ├─ ok    → frequencyStats = data.stats ?? []
  ├─ !ok   → frequencyError = "Failed to load statistics ({status})…"
  └─ throw → frequencyError = "Network error…"
  finally  → frequencyLoading = false
```

---

## UI Rendering States

### Frequency Chart Section

| State | Condition | What renders |
|---|---|---|
| **Loading** | `frequencyLoading === true` | Centered "Loading..." text |
| **Error** | `frequencyError !== ''` | Red alert box with error message |
| **Empty** | `topSymptoms.length === 0` | "No symptoms logged in this period." |
| **Data** | otherwise | Ordered list of up to 10 bars |

### Symptom History Section

| State | Condition | What renders |
|---|---|---|
| **Loading** | `loading === true` | Centered "Loading your history..." text |
| **Error** | `error !== ''` | Red alert box with error message |
| **Empty** | `dayGroups.length === 0` | Dashed-border empty state with CTA to `/log` |
| **Data** | otherwise | Ordered list of `DayGroup` cards |

---

## Bar Chart Implementation

Each bar row uses a three-column flex layout:

```
[name — w-36, right-aligned, truncated] [track — flex-1, h-5] [count — w-6]
```

Bar fill width is calculated inline:

```svelte
style="width: {(stat.count / maxCount) * 100}%"
```

- The longest bar always renders at 100% width (`maxCount` = top symptom's count).
- `aria-hidden="true"` on the fill div keeps the bar purely visual; the count label carries the accessible value.
- `title={stat.symptom_name}` on the name span provides a tooltip for truncated names.

---

## groupByDay Helper

Takes the flat `Log[]` array and returns `DayGroup[]` sorted newest-first.

```
For each log:
  1. Convert logged_at (ISO string) → local YYYY-MM-DD key via en-CA locale
  2. Bucket log under that key

For each bucket:
  3. Deduplicate symptoms by ID across all logs for the day
  4. Collect free-text entries (logs where free_text_entry != null)
  5. Format times with toLocaleTimeString('en-US', {hour, minute})
  6. Build DayGroup with label from dayLabel()

Sort: b.date.localeCompare(a.date) — newest-first (YYYY-MM-DD lexicographic order works correctly)
```

**dayLabel()** returns smart relative labels:

| Condition | Label |
|---|---|
| `dateKey === todayKey` | `"Today"` |
| `dateKey === yesterdayKey` | `"Yesterday"` |
| Same year as now | `"March 15"` |
| Different year | `"March 15, 2023"` |

DST edge case: dates are parsed at noon local time (`${dateKey}T12:00:00`) to avoid midnight boundary issues.

---

## Notes Toggle

Free-text notes are collapsible per day, controlled by `expandedNotes[group.date]`:

```typescript
function toggleNotes(date: string) {
    expandedNotes[date] = !expandedNotes[date];
}
```

The `expandedNotes` object is reset to `{}` in `fetchAll()` so all notes collapse when the date range changes.

Svelte's `transition:slide={{ duration: 200 }}` animates the notes list open/closed.

---

## TypeScript Interfaces

```typescript
interface SymptomDetail {
    id: string;
    name: string;
    category: string;
}

interface Log {
    id: string;
    user_id: string;
    logged_at: string;          // ISO 8601 timestamp string
    symptoms: SymptomDetail[];
    free_text_entry: string | null;
    source: string;             // 'cards' | 'text' | 'both'
}

interface SymptomFrequency {
    symptom_id: string;
    symptom_name: string;
    category: string;
    count: number;              // total occurrences, not unique days
}

interface FreeTextEntry {
    text: string;
    time: string;               // formatted, e.g. "2:30 PM"
    logId: string;
}

interface DayGroup {
    date: string;               // YYYY-MM-DD, used as key
    label: string;              // "Today" | "Yesterday" | "March 15" | …
    logCount: number;           // total raw logs for this day
    symptoms: SymptomDetail[];  // deduplicated across all logs
    freeTextEntries: FreeTextEntry[];
}
```

---

## Dependencies

| Import | Source | Purpose |
|---|---|---|
| `slide` | `svelte/transition` | Animate notes expand/collapse |
| `supabase` | `$lib/supabase/client` | Get auth session |

No shadcn-svelte components used — all UI is Tailwind utility classes.

---

## Styling Reference

**Section cards:** `rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm`

**Symptom pills (history):** `rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-sm font-medium text-teal-700`

**Bar track:** `h-5 flex-1 overflow-hidden rounded bg-teal-50`

**Bar fill:** `absolute inset-y-0 left-0 rounded bg-teal-500`

**Error box:** `rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700`

**Empty state (history):** `rounded-2xl border border-dashed border-slate-300 bg-slate-50 py-16 text-center`

**Date range dropdown:** `rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm` with `focus:border-teal-400 focus:ring-2 focus:ring-teal-200`

---

## Accessibility

- `<section aria-labelledby="freq-chart-heading">` on the chart card
- `<ol aria-label="Symptom frequency chart">` on the bar list
- `aria-hidden="true"` on the decorative bar fill element
- `title={stat.symptom_name}` tooltip on truncated symptom names
- `aria-expanded={notesExpanded}` on the notes toggle button
- `<ol aria-label="Journal entries">` on the notes list
- Focus ring on notes toggle: `focus-visible:ring-2 focus-visible:ring-teal-300`
- Heading hierarchy: `h1` (page title) → `h2` (day group labels)

---

## Error Handling

| Scenario | History section | Chart section |
|---|---|---|
| No auth session | `error = 'Please sign in…'` | `frequencyError = 'Please sign in…'` |
| HTTP error | `error = 'Failed to load… ({status})'` | `frequencyError = 'Failed to load… ({status})'` |
| Network error (fetch throws) | `error = 'Network error…'` | `frequencyError = 'Network error…'` |

Errors in one section do not affect the other — each has independent try/catch and finally blocks.

---

## Constants

```typescript
const API_BASE = 'http://localhost:8000';
```

Hardcoded for V1 local development. Before production, move to `$env/static/public` (e.g. `PUBLIC_API_URL`).

---

## V2 Notes

- **`API_BASE` env var:** Replace hardcoded localhost with `PUBLIC_API_URL` from `.env`.
- **Today's log CTA:** If the user hasn't logged today, show a prominent "Log today's symptoms" banner in the header row (DESIGN.md §10.3).
- **Logging streak heatmap:** GitHub-style calendar heat map (DESIGN.md §10.3, header row).
- **Co-occurrence card:** "Symptoms that travel together" section below the chart (DESIGN.md §10.3).
- **AI insight card:** "Generate My Insight" LLM narrative card (DESIGN.md §10.3).
- **Personalised chart order:** The frequency chart already surfaces personal patterns — the logging UI could use this data to reorder cards by personal frequency (currently uses global `sort_order`).
- **Custom date range picker:** DESIGN.md specifies a date range picker in addition to the preset 7/14/30 day options.
