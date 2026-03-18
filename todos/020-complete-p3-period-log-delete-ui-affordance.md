---
status: pending
priority: p3
issue_id: "020"
tags: [code-review, frontend, agent-native, ux]
dependencies: []
---

# Add delete affordance in PeriodLogModal (or document delete as agent-only)

## Problem Statement

`DELETE /api/period/logs/{id}` exists in the backend and is accessible to agents/API consumers, but there is no delete button in `PeriodLogModal.svelte`. Users who log a period by mistake have no way to delete it from the UI. This creates asymmetry: agents have more capability than the UI implies.

## Findings

- `backend/app/api/routes/period.py:89` — `DELETE /api/period/logs/{id}` exists
- `frontend/src/lib/components/period/PeriodLogModal.svelte` — no delete option when editing
- Agent-native reviewer flagged: "reverse agent-native problem — agent can delete, user cannot"

## Proposed Solutions

### Option 1: Add delete button to PeriodLogModal edit mode

**Approach:** When `existingLog` is non-null (edit mode), show a "Delete log" link/button with two-step inline confirmation (matches the conversation history delete pattern).

**Pros:** Closes UX gap, uses established confirmation pattern from history page

**Effort:** 1 hour

**Risk:** Low

---

### Option 2: Document delete as intentionally API/agent-only for V1

**Approach:** Add a comment in `PeriodLogModal.svelte` noting that delete is intentionally omitted from the UI in V1. Update CLAUDE.md or API docs to note the asymmetry.

**Pros:** Zero code change

**Cons:** Users have no self-service path for accidental logs

**Effort:** 5 minutes

**Risk:** None

## Recommended Action

Option 1 if UX matters for V1; Option 2 if this is explicitly deferred. Add the issue to the V2 backlog at minimum.

## Technical Details

**Affected files:**
- `frontend/src/lib/components/period/PeriodLogModal.svelte` — add delete UI in edit mode
- `frontend/src/routes/(app)/period/+page.svelte` — handle delete callback (remove log from list)

## Acceptance Criteria

- [ ] Edit mode shows "Delete log" option with confirmation
- [ ] Confirmed delete calls `DELETE /api/period/logs/{id}` and removes from calendar
- [ ] OR: documented as intentionally deferred to V2 with a backlog item

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
