# Onboarding UI — Developer Documentation

**Route:** `/onboarding`
**File:** `frontend/src/routes/(auth)/onboarding/+page.svelte`
**Phase:** V1
**Last Updated:** February 2026

---

## Overview

The onboarding page is a one-time questionnaire shown to new users immediately after Supabase Auth signup. It collects a date of birth and journey stage, then POSTs to the backend to create the user's profile row in `public.users`.

This page lives inside the `(auth)` route group, which has no navigation shell — it renders in a clean full-screen layout. No `+page.server.ts` or `+page.ts` load function is used; all logic runs client-side inside `onMount`.

---

## Related Documentation

- **Backend API contract:** [`docs/dev/backend/onboarding-api.md`](../backend/onboarding-api.md)
- **Data models:** [`docs/dev/DESIGN.md §9`](../DESIGN.md#9-data-models)
- **UX specification:** [`docs/dev/DESIGN.md §10.1`](../DESIGN.md#101-onboarding)
- **User guide:** [`docs/user/how-to-onboarding.md`](../../user/how-to-onboarding.md)

---

## State Model

All state is managed with Svelte 5 runes. There is no external store; all state is local to the component.

### Reactive State (`$state`)

| Variable | Type | Description |
|---|---|---|
| `dateOfBirth` | `string` | Raw value from the date input (`YYYY-MM-DD`). Empty string until the user enters a value. |
| `journeyStage` | `JourneyStage \| ''` | Selected radio value. Empty string until the user picks one. |
| `disclaimerAcknowledged` | `boolean` | Whether the user has ticked the medical disclaimer checkbox. |
| `loading` | `boolean` | True while the POST is in-flight; disables the submit button. |
| `error` | `string` | API or network error message shown below the form (empty = no error). |
| `dobError` | `string` | Client-side validation message shown under the date field (empty = no error). |
| `success` | `boolean` | True after a successful API response; triggers the success view and auto-redirect. |
| `checkingAuth` | `boolean` | True during the `onMount` auth + profile check; shows a loading state to prevent flash. |

### Derived State (`$derived`)

| Variable | Type | Logic |
|---|---|---|
| `canSubmit` | `boolean` | `dateOfBirth !== '' && journeyStage !== '' && disclaimerAcknowledged && dobError === '' && !loading` |

### Constants

```typescript
const API_BASE = 'http://localhost:8000'; // Replace with PUBLIC_API_URL env var for production
const todayStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD, used as date input max
```

### TypeScript Types

```typescript
type JourneyStage = 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';

const stages: { value: JourneyStage; label: string; description: string }[] = [
    { value: 'perimenopause', label: 'Perimenopause', description: '...' },
    { value: 'menopause',     label: 'Menopause',     description: '...' },
    { value: 'post-menopause', label: 'Post-menopause', description: '...' },
    { value: 'unsure',        label: 'Not sure',      description: '...' },
];
```

---

## Data Flow

### On Mount

```
onMount()
  ├─ supabase.auth.getSession()
  │    ├─ session is null → goto('/login')         [not authenticated]
  │    └─ session exists →
  │         supabase.from('users').select('id').eq('id', session.user.id).maybeSingle()
  │              ├─ profile found → goto('/dashboard')  [already onboarded]
  │              ├─ profile null  → checkingAuth = false  [show form]
  │              └─ error (e.g. invalid token) → catch → checkingAuth = false  [show form]
  └─ (any unexpected error) → catch → checkingAuth = false
```

The `catch` block intentionally shows the form on auth-check failure rather than leaving the user stuck on the loading screen. The backend will enforce auth again on submit.

### Date of Birth Validation

`validateDob()` is called on both `onchange` and `onblur` of the date input:

```
validateDob()
  ├─ dateOfBirth is empty → dobError = ''  (clear, no-op)
  ├─ parsed date >= today → dobError = 'Date of birth must be in the past.'
  └─ calculated age < 18  → dobError = 'You must be at least 18 years old to use Meno.'
```

Age is calculated accurately by checking whether the birthday has already occurred in the current year, avoiding off-by-one errors around birthdays:

```typescript
let age = today.getFullYear() - dob.getFullYear();
const monthDiff = today.getMonth() - dob.getMonth();
if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age--;
}
```

The date input is parsed as **local time** (using `new Date(year, month - 1, day)`) to avoid the timezone shift that occurs when parsing ISO strings directly with `new Date("YYYY-MM-DD")`, which are interpreted as UTC midnight.

### On Submit

```
handleSubmit()
  ├─ Guard: !canSubmit → return early
  ├─ supabase.auth.getSession() → get JWT access_token
  │    └─ no token → error = 'session expired', goto('/login')
  ├─ POST http://localhost:8000/api/users/onboarding
  │    Headers: { Authorization: Bearer <token>, Content-Type: application/json }
  │    Body:    { date_of_birth: 'YYYY-MM-DD', journey_stage: string }
  ├─ response.status === 409 → goto('/dashboard')  [already onboarded, silent redirect]
  ├─ response.status === 400 → error = errorData.detail  [validation message from API]
  ├─ !response.ok (other) → error = errorData.detail ?? generic message
  ├─ response.ok → success = true, setTimeout(() => goto('/dashboard'), 1200)
  └─ fetch throws (network error) → error = 'Network error…'
```

---

## UI Rendering States

The template has three mutually exclusive top-level states:

| State | Condition | What renders |
|---|---|---|
| **Checking auth** | `checkingAuth === true` | Full-screen centred "Loading…" text |
| **Success** | `success === true` | Full-screen emerald checkmark + "You're all set!" + auto-redirect |
| **Form** | default | Header, disclaimer box, date + journey stage form, submit button |

---

## Form Components

### Medical Disclaimer

An amber `bg-amber-50 border-amber-200` info box with:
- An info icon (SVG)
- The Meno disclaimer text
- An "I understand" checkbox (`bind:checked={disclaimerAcknowledged}`)

The checkbox must be ticked before `canSubmit` becomes true. This is enforced client-side only (the API does not require a disclaimer field).

### Date of Birth Field

- `type="date"` input with `max={todayStr}` to prevent future dates via the browser picker
- `onchange={validateDob}` and `onblur={validateDob}` for immediate inline feedback
- Border turns red (`border-red-300`) and helper text turns red when `dobError` is set

### Journey Stage

A `<fieldset>` with four full-width radio card `<label>` elements. Each card:
- Wraps a visually-styled `<input type="radio">` with `bind:group={journeyStage}`
- Highlights with `border-violet-400 bg-violet-50` when selected
- Displays the stage label + descriptive subtitle

The entire card area is clickable (the `<label>` wraps the radio input), making it easy to tap on touch devices.

### Submit Button

- `type="submit"` inside a `<form onsubmit={...}>` for semantic HTML
- `disabled={!canSubmit}` — greyed out (`bg-slate-200 text-slate-400`) until all conditions pass
- Shows "Setting up your account…" during the loading state

---

## Animations

| Element | Transition | Parameters |
|---|---|---|
| Page fade-in (form view) | `in:fade` | `{ duration: 150 }` |
| Success view | `in:fade` | `{ duration: 200 }` |
| DOB validation error | `in:fly` | `{ y: -4, duration: 150 }` |
| API error message | `in:fly` | `{ y: -4, duration: 150 }` |

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| No session on mount | `goto('/login')` |
| Profile exists on mount | `goto('/dashboard')` |
| Auth check throws (e.g. invalid token) | `catch` → show form; backend validates on submit |
| No session token at submit | `error` message → `goto('/login')` |
| API 409 (duplicate) | `goto('/dashboard')` silently |
| API 400 (validation) | Show `errorData.detail` inline |
| API other non-2xx | Show `errorData.detail` or generic fallback |
| Network error (fetch throws) | Show "Network error…" message |
| `response.json()` parse fails | `.catch(() => ({}))` prevents secondary error |

---

## Dependencies

| Import | Source | Purpose |
|---|---|---|
| `onMount` | `svelte` | Auth check and profile query after mount |
| `goto` | `$app/navigation` | Programmatic redirects |
| `fly`, `fade` | `svelte/transition` | Error and state transition animations |
| `supabase` | `$lib/supabase/client` | Auth session retrieval and profile existence check |

No shadcn-svelte components are used — all UI is Tailwind utility classes.

---

## Accessibility

- Medical disclaimer uses an `<input type="checkbox">` with an associated `<label>` (wrapping pattern)
- Journey stage uses a `<fieldset>` with a `<legend>` for screen reader grouping
- Each radio card is a `<label>` wrapping a real `<input type="radio">` — fully keyboard-navigable
- DOB validation error and API error have `role="alert"` for screen reader announcement
- All SVG icons have `aria-hidden="true"`

---

## V2 Notes

- **`API_BASE` env var:** Replace hardcoded `localhost:8000` with `PUBLIC_API_URL` from `.env`.
- **Journey stage recalculation:** DESIGN.md §10.1 notes that in V2, `journey_stage` becomes calculated from period tracking data rather than self-reported. The onboarding form will drop this field.
- **Magic link auth:** V2 switches from password auth to magic links; the login → onboarding redirect path may change.
- **Feature tour:** DESIGN.md §10.1 specifies a skippable feature tour after the questionnaire (currently deferred).
