---
status: pending
priority: p3
issue_id: "024"
tags: [code-review, frontend, data-safety]
dependencies: []
---

# Guard `months_since_last_period` against negative values before rendering

## Problem Statement

`period/+page.svelte` renders `{cycleAnalysis?.months_since_last_period} months` directly. The `months_since_date()` utility returns a negative integer if the date is in the future. While `create_log` rejects future `period_start` dates at the service layer, edge cases (DST, timezone drift, or existing data) could produce a negative value. Rendering "-3 months" undermines user trust.

## Findings

- `frontend/src/routes/(app)/period/+page.svelte:155` — renders `months_since_last_period` verbatim
- `backend/app/utils/dates.py` — `months_since_date` uses simple arithmetic, can return negative
- Security sentinel flagged as Low

## Proposed Solutions

### Option 1: `Math.max(0, ...)` guard on render

```svelte
You haven't logged a period in {Math.max(0, cycleAnalysis?.months_since_last_period ?? 0)} months.
```

**Effort:** 2 minutes

**Risk:** None

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/period/+page.svelte:155`

Also consider: cycle summary card at line 200-203 renders the same value — add the same guard there.

## Acceptance Criteria

- [ ] Inference banner never renders a negative number of months
- [ ] Cycle summary card never renders a negative number of months

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
