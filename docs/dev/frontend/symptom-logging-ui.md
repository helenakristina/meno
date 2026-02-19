# Symptom Logging UI — Developer Documentation

**Route:** `/log`
**File:** `frontend/src/routes/(app)/log/+page.svelte`
**Phase:** V1
**Last Updated:** February 2026

---

## Overview

The symptom logging page is the core daily-use feature of Meno. It presents a card-based UI for selecting symptoms from a curated reference list, a free-text entry area for additional context, and submits to the backend REST API.

This page lives inside the `(app)` layout group, which handles authentication guard and navigation. The page itself is always rendered client-side; no `+page.server.ts` or `+page.ts` load function is used — all data fetching happens in `onMount`.

---

## Related Documentation

- **Backend API contract:** [`docs/dev/backend/symptom-logging-api.md`](../backend/symptom-logging-api.md)
- **Data models:** [`docs/dev/DESIGN.md §9`](../DESIGN.md#9-data-models)
- **UX specification:** [`docs/dev/DESIGN.md §10.2`](../DESIGN.md#102-daily-symptom-logging)
- **User guide:** [`docs/user/how-to-log-symptoms.md`](../../user/how-to-log-symptoms.md)

---

## State Model

All state is managed with Svelte 5 runes (`$state`, `$derived`). There is no external store; all state is local to the component and resets on page navigation.

### Reactive State (`$state`)

| Variable | Type | Description |
|---|---|---|
| `allSymptoms` | `Symptom[]` | Full list fetched from `symptoms_reference` on mount, ordered by `sort_order` |
| `selectedSymptoms` | `Symptom[]` | Symptoms the user has tapped to log; appears as chips in the tray |
| `dismissedIds` | `string[]` | UUIDs of cards the user has dismissed this session; not persisted |
| `freeText` | `string` | Contents of the optional textarea |
| `loadingSymptoms` | `boolean` | True while Supabase fetch is in-flight; shows loading state |
| `submitting` | `boolean` | True while POST is in-flight; disables submit button |
| `error` | `string` | Inline error message (empty string = no error shown) |
| `success` | `boolean` | True after a successful save; shows confirmation panel |

### Derived State (`$derived`)

| Variable | Type | Logic |
|---|---|---|
| `availableSymptoms` | `Symptom[]` | `allSymptoms` filtered to exclude selected and dismissed IDs |
| `visibleCards` | `Symptom[]` | First `CARDS_VISIBLE` (8) items of `availableSymptoms` |
| `poolExhausted` | `boolean` | `availableSymptoms.length === 0` |
| `canSubmit` | `boolean` | `selectedSymptoms.length > 0 \|\| freeText.trim().length > 0` |
| `source` | `'cards' \| 'text' \| 'both'` | Derived from which inputs have content (see Source Field below) |

The card pool replenishes automatically: because `visibleCards` is derived from `availableSymptoms`, removing a symptom (by selecting or dismissing) immediately makes the next symptom in sort order slide in — no imperative queue management needed.

---

## Data Flow

### On Mount

```
onMount()
  └─ supabase.from('symptoms_reference').select('*').order('sort_order')
       ├─ success → allSymptoms = data          (derived state takes over)
       └─ error   → error = 'Failed to load…'
```

The component fetches directly from Supabase using the public anon key (client-side). The `symptoms_reference` table has no RLS — it's public reference data readable by all authenticated users.

### Card Interactions

```
User clicks card body
  └─ selectCard(symptom)
       └─ selectedSymptoms = [...selectedSymptoms, symptom]
            └─ availableSymptoms $derived updates → visibleCards $derived updates
                 └─ next card in pool slides in via fly transition

User clicks dismiss X
  └─ dismissCard(symptom)
       └─ dismissedIds = [...dismissedIds, symptom.id]
            └─ same derived cascade as above

User clicks chip X
  └─ deselectChip(symptom)
       └─ selectedSymptoms = selectedSymptoms.filter(s => s.id !== symptom.id)
            └─ symptom returns to available pool → card reappears
```

### On Submit

```
handleSubmit()
  ├─ Guard: !canSubmit || submitting → return early
  ├─ supabase.auth.getSession() → get JWT access_token
  ├─ Derive source field from current state
  ├─ POST http://localhost:8000/api/symptoms/logs
  │    Headers: Authorization: Bearer <token>, Content-Type: application/json
  │    Body: { source, symptoms: UUID[], free_text_entry: string | null }
  ├─ response.ok → success = true, reset form state
  └─ !response.ok → parse errorData.detail, set error string
```

---

## Source Field Logic

The `source` field is required by the API and determined automatically:

| `selectedSymptoms` | `freeText` | `source` sent |
|---|---|---|
| non-empty | non-empty | `"both"` |
| non-empty | empty | `"cards"` |
| empty | non-empty | `"text"` |

When `source = "text"`, `symptoms` is sent as `[]` (the API ignores it for text-only logs).

---

## UI Rendering States

The template has four mutually exclusive top-level states:

| State | Condition | What renders |
|---|---|---|
| **Loading** | `loadingSymptoms === true` | Centered "Loading symptoms..." text |
| **Success** | `success === true` | Green confirmation panel with checkmark and "Log more symptoms" reset |
| **Pool exhausted + nothing selected** | `poolExhausted && selectedSymptoms.length === 0` | Dashed empty-state box, textarea, disabled submit |
| **Normal** (default) | otherwise | Card grid + optional tray + textarea + submit |

The selected tray is conditionally rendered within the normal state: it appears only when `selectedSymptoms.length > 0`.

---

## Animations

Uses `fly` and `fade` from `svelte/transition`. All transitions are keyed on `symptom.id` in `{#each}` blocks.

| Element | Transition | Parameters |
|---|---|---|
| Cards entering | `in:fly` | `{ y: 10, duration: 200 }` |
| Cards leaving | `out:fly` | `{ y: -6, duration: 150 }` |
| Selected chips entering | `in:fly` | `{ x: -4, duration: 150 }` |
| Selected chips leaving | `out:fade` | `{ duration: 100 }` |
| Tray section appearing | `in:fly` | `{ y: 6, duration: 200 }` |
| Success panel | `in:fly` | `{ y: -10, duration: 300 }` |
| Error message | `in:fly` | `{ y: -4, duration: 200 }` |
| Pool-exhausted empty state | `in:fade` | `{ duration: 200 }` |

---

## Constants

```typescript
const CARDS_VISIBLE = 8;   // cards shown at once; adjust for UX feel
const API_BASE = 'http://localhost:8000';  // move to env var for production
```

`API_BASE` is hardcoded for V1 local development. Before production, this should be read from `$env/static/public` (e.g. `PUBLIC_API_URL`).

---

## TypeScript Interface

```typescript
interface Symptom {
    id: string;       // UUID from symptoms_reference.id
    name: string;     // Display name, e.g. "Hot flashes"
    category: string; // 'vasomotor' | 'sleep' | 'mood' | 'cognitive' | 'physical' | 'urogenital' | 'skin_hair'
    sort_order: number;
}
```

---

## Dependencies

| Import | Source | Purpose |
|---|---|---|
| `onMount` | `svelte` | Trigger Supabase fetch after component mounts |
| `fly`, `fade` | `svelte/transition` | Card and chip animations |
| `supabase` | `$lib/supabase/client` | Fetch symptoms reference + get auth session |

No shadcn-svelte components are used — all UI is built with Tailwind utility classes for maximum control over the interactive card states.

---

## Accessibility

- Card grid is wrapped in `<section aria-label="Available symptoms">`
- Selected tray is wrapped in `<section aria-label="Selected symptoms">`
- Dismiss buttons have `aria-label="Dismiss {card.name}"`
- Chip remove buttons have `aria-label="Remove {symptom.name}"`
- All SVG icons have `aria-hidden="true"`
- Focus rings use `focus-visible:ring-2` (only shown on keyboard navigation)

---

## Error Handling

| Scenario | UI behaviour |
|---|---|
| Supabase fetch fails on mount | `error` message shown; no cards rendered |
| No auth session at submit time | `error = 'You must be signed in…'`; submitting stops |
| API returns non-2xx | `errorData.detail` displayed, or generic `Error {status}` fallback |
| Network error (fetch throws) | `'Network error. Please check your connection…'` displayed |
| `response.json()` parse fails | `.catch(() => ({}))` prevents secondary error; generic message shown |

---

## V2 Notes

- **Personalised sort order:** In V1, cards always appear in global `sort_order`. V2 should reorder by the user's personal most-frequently-logged symptoms (requires a stats query).
- **Session persistence of dismissals:** Dismissed cards currently reset on refresh. V2 could store `dismissedIds` in `sessionStorage`.
- **`API_BASE` env var:** Replace hardcoded `localhost:8000` with `PUBLIC_API_URL` from `.env`.
- **Today's log detection:** V2 dashboard should check whether the user has already logged today and deep-link to the log page with a CTA.
