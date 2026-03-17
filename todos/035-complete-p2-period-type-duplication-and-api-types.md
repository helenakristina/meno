---
status: pending
priority: p2
issue_id: "035"
tags: [code-review, typescript, frontend, type-safety]
dependencies: []
---

# `PeriodLog` / `FlowLevel` types duplicated 3x + GET logs missing from ApiEndpoints

## Problem Statement

1. `FlowLevel` and `PeriodLog` types are defined identically in `PeriodCalendar.svelte`, `PeriodLogModal.svelte`, and `period/+page.svelte`. Any schema change requires 3 edits with no compile-time guarantee they stay in sync.

2. `GET /api/period/logs` is not in `ApiEndpoints` in `api.ts` — only POST is registered. The page uses manual type casts (`as { logs: PeriodLog[]; total: number }`) instead of the typed client.

3. `PATCH /api/period/logs/{id}` is also missing from `ApiEndpoints`.

## Findings

- `frontend/src/lib/components/period/PeriodCalendar.svelte:10-20`
- `frontend/src/lib/components/period/PeriodLogModal.svelte:5-15`
- `frontend/src/routes/(app)/period/+page.svelte:10-20`
- `frontend/src/lib/types/api.ts` — missing GET and PATCH for period logs

## Proposed Solution

1. Create `frontend/src/lib/types/period.ts` with `FlowLevel`, `PeriodLog`, `CycleAnalysis`
2. Add to `ApiEndpoints`:
   - `GET /api/period/logs` → `{ logs: PeriodLog[]; total: number }`
   - `PATCH /api/period/logs/{id}` → `PeriodLog`

## Acceptance Criteria
- [ ] Types defined once, imported everywhere
- [ ] GET and PATCH period log endpoints in ApiEndpoints
- [ ] No manual `as` casts for period API responses
