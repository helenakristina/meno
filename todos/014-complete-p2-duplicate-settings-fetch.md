---
status: pending
priority: p2
issue_id: "014"
tags: [code-review, frontend, performance]
dependencies: []
---

# Eliminate duplicate `/api/users/settings` fetch between layout and period page

## Problem Statement

`+layout.svelte` fetches `/api/users/settings` on mount to determine whether to show the Cycles nav link. `period/+page.svelte` fetches the same endpoint again in `loadData()` to get `journey_stage` for the inference banner. Every Cycles page load makes two identical network requests to the same endpoint.

## Findings

- `frontend/src/routes/(app)/+layout.svelte:34` — fetches settings on mount
- `frontend/src/routes/(app)/period/+page.svelte:58` — also fetches settings in `loadData()`
- Performance reviewer flagged
- Same data fetched twice in parallel on every Cycles page load

## Proposed Solutions

### Option 1: Svelte store for user settings

**Approach:** Create `frontend/src/lib/stores/settings.ts` — a writable store that caches the settings response. Layout fetches once and writes to the store. Period page reads from the store (or triggers a fetch if the store is empty).

```typescript
// src/lib/stores/settings.ts
export const userSettings = writable<UserSettings | null>(null);
```

**Pros:** Single fetch, shared across all pages, consistent pattern with `auth.ts` store

**Cons:** Needs a store module; staleness handling if settings change

**Effort:** 45 minutes

**Risk:** Low

---

### Option 2: Load settings in the layout's `+layout.ts` load function

**Approach:** Use SvelteKit's server-side `load()` in `+layout.ts` to fetch settings once and pass via `data` props to all child routes.

**Pros:** SvelteKit-idiomatic, settings available before page renders

**Cons:** Requires restructuring to use SvelteKit load functions (bigger change)

**Effort:** 2 hours

**Risk:** Medium

## Recommended Action

Option 1: a lightweight writable store. This project already has an `auth.ts` store — follow the same pattern. Low risk, immediate impact.

## Technical Details

**Affected files:**
- NEW: `frontend/src/lib/stores/settings.ts`
- `frontend/src/routes/(app)/+layout.svelte` — write to store after fetch
- `frontend/src/routes/(app)/period/+page.svelte` — read from store instead of fetching

## Acceptance Criteria

- [ ] Only one `/api/users/settings` request on Cycles page load
- [ ] Layout and period page share the same settings data
- [ ] Settings store updates when settings are changed (e.g., after PATCH)

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Confirmed duplicate fetch via network request analysis
- Identified settings store as the lowest-friction fix
