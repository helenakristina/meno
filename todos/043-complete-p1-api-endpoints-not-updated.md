---
status: complete
priority: p1
issue_id: "043"
tags: [code-review, frontend, typescript, type-safety, medications, pr-2]
dependencies: []
---

# `ApiEndpoints` not updated — `mht_tracking_enabled` and `/api/medications` missing

## Problem Statement

The typed API client contract (`ApiEndpoints` in `src/lib/types/api.ts`) was not updated with the new `mht_tracking_enabled` field or the new `/api/medications` endpoint. This forces multiple `as` type casts at call sites, breaking type safety completely for the new features.

## Findings

Three distinct issues, all rooting in `api.ts`:

1. **`mht_tracking_enabled` missing from settings response type** — `+layout.svelte` lines 36–44 casts result as inline type without `mht_tracking_enabled`, discarding the typed client contract
2. **`mht_tracking_enabled` missing from settings request type** — `settings/+page.svelte` calls `apiClient.patch('/api/users/settings', { mht_tracking_enabled: ... })` but the field isn't in the `ApiEndpoints` request union
3. **`/api/medications` not registered** — `medications/+page.svelte` calls `apiClient.get('/api/medications')` with `as Medication[]` cast, providing zero type safety

Identified by TypeScript reviewer and agent-native reviewer.

## Proposed Solutions

### Option 1: Update `ApiEndpoints` in `api.ts` (Recommended)

1. Add `mht_tracking_enabled: boolean` to the response shape for `/api/users/settings`
2. Add `mht_tracking_enabled?: boolean` to the request shape for `/api/users/settings`
3. Add `/api/medications` to `ApiEndpoints` with `MedicationListResponse` as response type
4. Remove all `as` casts from `+layout.svelte`, `settings/+page.svelte`, and `medications/+page.svelte`

**Pros:** Fixes all three issues together, restores type safety, IDE autocomplete works
**Effort:** Small — concentrated in `api.ts`
**Risk:** Low

## Recommended Action

Option 1 — all three issues have the same root cause and the same fix location.

## Technical Details

**Affected files:**
- `frontend/src/lib/types/api.ts` — add field to settings types, add `/api/medications` entry
- `frontend/src/routes/(app)/+layout.svelte` lines 36–44 — remove cast
- `frontend/src/routes/(app)/settings/+page.svelte` — remove cast, use typed field
- `frontend/src/routes/(app)/medications/+page.svelte` line 34 — remove `as Medication[]` cast

**Also fix:** Extract a shared `UserSettings` TypeScript interface (referenced in `stores/settings.ts` and `+layout.svelte`) to eliminate the two separate inline type definitions for the same shape.

## Acceptance Criteria

- [ ] `ApiEndpoints['/api/users/settings'].response` includes `mht_tracking_enabled: boolean`
- [ ] `ApiEndpoints['/api/users/settings'].request` includes `mht_tracking_enabled?: boolean`
- [ ] `ApiEndpoints['/api/medications']` is registered with correct response type
- [ ] No `as SomeType` casts in `+layout.svelte`, `settings/+page.svelte`, `medications/+page.svelte`
- [ ] TypeScript strict mode compiles with zero errors

## Work Log

- 2026-03-18: Identified by TypeScript reviewer and agent-native reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready

## Resources

- PR #2: feat/mht-medication-tracking
- `frontend/src/lib/types/api.ts`
- Memory: `docs/dev/frontend/V2CODE_EXAMPLES.md` Part 11 typed client
