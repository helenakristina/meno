---
status: pending
priority: p3
issue_id: "016"
tags: [code-review, frontend, type-safety, cleanup]
dependencies: []
---

# Deduplicate `PeriodLog` and `FlowLevel` types — defined in 3 frontend files

## Problem Statement

`FlowLevel` and `PeriodLog` types are copy-pasted identically across three frontend files: `PeriodCalendar.svelte`, `PeriodLogModal.svelte`, and `period/+page.svelte`. These should be defined once in `api.ts` or a shared types file and imported.

## Findings

- `frontend/src/lib/components/period/PeriodCalendar.svelte:10-20`
- `frontend/src/lib/components/period/PeriodLogModal.svelte:5-15`
- `frontend/src/routes/(app)/period/+page.svelte:8-18`
- All three define identical `FlowLevel = 'spotting' | 'light' | 'medium' | 'heavy'` and near-identical `PeriodLog` shapes
- TypeScript reviewer and code simplicity reviewer both flagged

## Proposed Solutions

### Option 1: Extract to `frontend/src/lib/types/period.ts`

**Approach:** Create a new shared types file and import in all three components.

```typescript
// src/lib/types/period.ts
export type FlowLevel = 'spotting' | 'light' | 'medium' | 'heavy';
export type PeriodLog = { id: string; period_start: string; ... };
```

**Pros:** Single source of truth, type changes propagate automatically

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Derive from `api.ts` response type

**Approach:** The `/api/period/logs` response type in `api.ts` already defines the log shape. Extract `PeriodLog` from that.

**Pros:** Stays aligned with API contract

**Cons:** `api.ts` types are defined as nested response fields; requires `ApiResponse<'/api/period/logs'>['logs'][0]` which is verbose

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1: dedicated `types/period.ts` file. Cleaner import path than extracting from nested API response types.

## Technical Details

**Affected files:**
- NEW: `frontend/src/lib/types/period.ts`
- `frontend/src/lib/components/period/PeriodCalendar.svelte` — remove local type defs, add import
- `frontend/src/lib/components/period/PeriodLogModal.svelte` — remove local type defs, add import
- `frontend/src/routes/(app)/period/+page.svelte` — remove local type defs, add import

## Acceptance Criteria

- [ ] `FlowLevel` defined in one place
- [ ] `PeriodLog` defined in one place
- [ ] All three files import from shared location
- [ ] No TypeScript errors

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
