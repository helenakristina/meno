---
title: UTC Date Off-by-One — ISO Date String Parsing in SvelteKit
category: runtime-errors
date: 2026-03-20
tags: [timezone, date-parsing, svelte, javascript, medication-tracking]
symptoms:
  - Date displays one day earlier than expected (e.g. "18 Mar" instead of "19 Mar")
  - Bug only affects users in timezones west of UTC
  - Correct date appears in raw form inputs (date picker shows right value) but wrong in formatted text
components:
  - frontend/src/routes/(app)/medications/+page.svelte
  - frontend/src/routes/(app)/medications/[id]/+page.svelte
  - frontend/src/routes/(app)/medications/[id]/impact/+page.svelte
---

## Problem

Date-only strings returned from the API (e.g. `"2026-03-19"`) displayed one day earlier in any timezone west of UTC. The medication list showed "Started 18 Mar 2026" when the correct date was 19 Mar.

## Root Cause

JavaScript's `new Date('2026-03-19')` treats a bare ISO date string (no time component) as **UTC midnight**. In US Eastern (UTC-5), UTC midnight is 7pm the previous day, so `toLocaleDateString()` returns March 18.

```javascript
// In US Eastern (UTC-5):
new Date('2026-03-19')
// → 2026-03-18T19:00:00 local
// → displays "18 Mar"  ❌
```

The bug was inconsistent across the codebase — dashboard, export, and providers pages already had the fix applied (`T12:00:00` appended); the three medication pages had not caught up.

## Fix

Append `T12:00:00` to date-only strings before constructing the `Date` object. This forces the parser to treat the timestamp as **local noon**, which is guaranteed to fall on the correct calendar day in any timezone (since no UTC offset exceeds ±12 hours).

```javascript
// BEFORE (broken in UTC- timezones)
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
}

// AFTER (correct in all timezones)
function formatDate(dateStr: string): string {
  return new Date(`${dateStr}T12:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
}
```

Applied the fix to all three medication pages, matching what dashboard/export/providers already did.

## Why `T12:00:00` Works

Local noon converted through any possible UTC offset (±12h max) always stays within the same calendar day:

| Timezone | UTC offset | `2026-03-19T12:00:00` local = |
|----------|-----------|-------------------------------|
| US Eastern | UTC-5 | 7am March 19 ✅ |
| US Pacific | UTC-8 | 4am March 19 ✅ |
| Tokyo | UTC+9 | 9pm March 19 ✅ |
| UTC | UTC+0 | noon March 19 ✅ |

## Safe vs. Unsafe Date Patterns

| Pattern | Safe? | Notes |
|---------|-------|-------|
| `new Date('2026-03-19')` | ❌ | UTC midnight → wrong day in UTC- zones |
| `new Date('2026-03-19T12:00:00')` | ✅ | Local noon → correct in all zones |
| `new Date(year, month - 1, day)` | ✅ | Local midnight via constructor → also correct |
| `new Date().toISOString().split('T')[0]` | ❌ | Returns UTC date, not local date |
| `today.getFullYear() + '-' + ...` | ✅ | Local date parts → correct |

## Prevention

**No shared date utility exists** (`src/lib/utils.ts` only has CSS helpers). Each component implements date handling independently, which is how drift happened.

**Checklist when formatting API dates:**
- [ ] Never pass a bare `YYYY-MM-DD` string directly to `new Date()`
- [ ] Always append `T12:00:00` when building a `Date` for display
- [ ] For form defaults ("today"), use local date parts not `toISOString()`

**Pattern for "today" as a date input default:**
```typescript
// ✅ Correct — local date
const today = new Date();
const startDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

// ❌ Wrong — UTC date
const startDate = new Date().toISOString().split('T')[0];
```

## Related

- Dashboard uses `new Date(\`${dateKey}T12:00:00\`)` — same fix, already applied
- Export uses `new Date(\`${dateStr}T12:00:00\`)` — same fix, already applied
- `frontend/src/lib/components/providers/ProviderCard.svelte` — same fix applied
