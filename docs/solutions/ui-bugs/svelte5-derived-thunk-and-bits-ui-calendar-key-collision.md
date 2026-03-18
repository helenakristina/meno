---
title: "Svelte 5 $derived thunk bug + bits-ui Calendar weekday key collision"
category: ui-bugs
date: 2026-03-17
tags: [svelte5, svelte, bits-ui, reactivity, derived, each-key, calendar]
modules: [PeriodCalendar, period-tracking]
symptoms:
  - "each_key_duplicate crash — SvelteError: Key 'T' is duplicated"
  - "Calendar renders logs on load but never updates after add/delete"
---

# Svelte 5 `$derived` thunk bug + bits-ui Calendar weekday key collision

Two distinct bugs, both in `PeriodCalendar.svelte`, both worth knowing.

## Bug 1: bits-ui Calendar weekdays produce duplicate `{#each}` keys

### Symptom

`SvelteError: each_key_duplicate. Key 'T' is duplicated in a keyed each block.`

Crash occurs on render whenever the calendar contains a Tuesday **and** a Thursday (both abbreviated to "T").

### Root Cause

`bits-ui`'s `Calendar` component passes weekdays as **single-character abbreviations** — `["S", "M", "T", "W", "T", "F", "S"]`. Tuesday and Thursday both produce `"T"`, causing a duplicate key error when the day string is used as the `{#each}` key.

### Solution

Use the loop index as the key, not the day string:

```svelte
<!-- ❌ Breaks: "T" appears twice -->
{#each weekdays as day (day)}

<!-- ✅ Fix: index is always unique -->
{#each weekdays as day, i (i)}
```

### Prevention

When iterating over any UI-library-provided list that may contain duplicate display values, always key by index or a stable unique ID — never by the display string itself.

---

## Bug 2: `$derived(() => {...})` creates a permanent function, not reactive state

### Symptom

Calendar displays period logs correctly on initial load, but adding or deleting a log does not update the calendar. The displayed state is frozen at mount time.

### Root Cause

`$derived` in Svelte 5 takes an **expression**, not a function. Writing `$derived(() => { ... })` evaluates the expression (an arrow function) once and stores the arrow function itself as the derived value — it is never re-evaluated when dependencies change.

```svelte
// ❌ Wrong: logByDate is a permanent arrow function
const logByDate = $derived(() => {
  const map = new Map<string, PeriodLog>();
  for (const log of logs) map.set(log.period_start, log);
  return map;
});

// Usage worked "by accident" — called as a function:
logByDate().get(key)  // ← NOT reactive
```

The calendar appeared to work on load because the function was called once, but subsequent log changes never triggered re-evaluation.

### Solution

Use `$derived.by()` for block-form derived state (returns the inner value directly):

```svelte
// ✅ Fix: $derived.by for block body
const logByDate = $derived.by(() => {
  const map = new Map<string, PeriodLog>();
  for (const log of logs) map.set(log.period_start, log);
  return map;
});

// Read as a value — no parens:
logByDate.get(key)  // ✅ reactive
```

Or inline for a simple case:

```svelte
const logByDate = $derived(new Map(logs.map(l => [l.period_start, l])));
```

### Svelte 5 `$derived` API Summary

| Form | When to use |
|---|---|
| `$derived(expr)` | Single expression — most cases |
| `$derived.by(() => { ... })` | Block body needed (loops, conditionals) |
| `$derived(() => { ... })` | **Never** — stores the function itself, not the result |

### Prevention

If you need a block body in a derived, always reach for `$derived.by`. The `$derived(() => ...)` form compiles without error and produces a value (the function), so TypeScript and the Svelte compiler won't warn you — it only shows up as stale UI at runtime.

Linting rule: treat any `$derived(() =>` as a code smell requiring review.

---

## Related Files

- `frontend/src/lib/components/period/PeriodCalendar.svelte` — both bugs found here
- Todo: `todos/001-pending-p1-derived-thunk-bug-period-calendar.md`
