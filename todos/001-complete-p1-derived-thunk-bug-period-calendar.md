---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, frontend, svelte5, reactivity]
dependencies: []
---

# Fix `$derived` thunk bug in PeriodCalendar — calendar never updates

## Problem Statement

`PeriodCalendar.svelte` uses `$derived(() => {...})` to build the log lookup map. In Svelte 5, `$derived` takes an **expression**, not a function. This means `logByDate` is a permanently-fixed arrow function value — not reactive state. The calendar will render logs on initial load but will **never update** when logs are added, edited, or deleted, because the derived never re-evaluates.

## Findings

- `frontend/src/lib/components/period/PeriodCalendar.svelte:33` — `const logByDate = $derived(() => { const map = new Map... return map; })`
- `logByDate` is called as a function (`logByDate()`) on line 43, which happens to work accidentally because the arrow function is returned as-is — but it is not reactive
- The correct Svelte 5 API for block-form derived is `$derived.by(() => { ... })` (returns the value) or an inline expression `$derived(new Map(logs.map(...)))`
- Confirmed by TypeScript reviewer and code simplicity reviewer

## Proposed Solutions

### Option 1: Use `$derived.by`

**Approach:** Change `$derived(() => {...})` to `$derived.by(() => {...})` and remove the `()` call on line 43.

```svelte
const logByDate = $derived.by(() => {
  const map = new Map<string, PeriodLog>();
  for (const log of logs) {
    map.set(log.period_start, log);
  }
  return map;
});

// usage: logByDate.get(key) — no parens
```

**Pros:** Minimal change, correct Svelte 5 semantics, map is reactive

**Cons:** None

**Effort:** 5 minutes

**Risk:** Low

---

### Option 2: Inline expression

**Approach:** `const logByDate = $derived(new Map(logs.map(l => [l.period_start, l])));`

**Pros:** One-liner, clearly reactive

**Cons:** Slightly less readable for complex init logic

**Effort:** 5 minutes

**Risk:** Low

## Recommended Action

Use Option 1 (`$derived.by`). Change line 33 from `$derived(` to `$derived.by(` and remove `()` call on line 43.

## Technical Details

**Affected files:**
- `frontend/src/lib/components/period/PeriodCalendar.svelte:33` — `$derived` call
- `frontend/src/lib/components/period/PeriodCalendar.svelte:43` — `logByDate()` call with parens

## Acceptance Criteria

- [ ] `logByDate` uses `$derived.by` or an equivalent inline expression
- [ ] Calendar re-renders when a log is added or deleted
- [ ] No `()` call on `logByDate` in the template

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified wrong `$derived` usage
- Confirmed with TypeScript reviewer and code simplicity reviewer
