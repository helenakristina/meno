---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, backend, security, validation]
dependencies: []
---

# Add `max_length` constraint to `notes` field in period log model and migration

## Problem Statement

`PeriodLogCreate.notes` and `PeriodLogUpdate.notes` have no length limit. The DB column is `TEXT` with no constraint. A user can submit megabytes of text per log entry. This creates storage abuse risk and — more importantly — an unbounded free-text field is a prompt injection surface if notes are ever passed to the LLM (e.g., a future "summarise my cycle" feature).

## Findings

- `backend/app/models/period.py:13-21` — `notes: Optional[str] = None` with no `Field(max_length=...)`
- `backend/migrations/add_period_tracking.sql:17` — `notes TEXT` with no constraint
- Every `GET /api/period/logs` response carries notes for all returned logs — large notes inflate response size
- Security sentinel flagged as Medium severity

## Proposed Solutions

### Option 1: 1000-char Pydantic limit + DB CHECK constraint

**Approach:**
1. `PeriodLogCreate.notes: str | None = Field(None, max_length=1000)`
2. `PeriodLogUpdate.notes: str | None = Field(None, max_length=1000)`
3. Add migration: `ALTER TABLE period_logs ADD CONSTRAINT notes_max_length CHECK (char_length(notes) <= 1000);`

**Pros:** Validated at API boundary AND database level (defence in depth)

**Cons:** Requires a new migration file

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Pydantic limit only

**Approach:** Add `Field(max_length=1000)` to model only, no DB constraint.

**Pros:** No migration needed

**Cons:** Not enforced at DB level — bypass possible via service role key

**Effort:** 15 minutes

**Risk:** Low

## Recommended Action

Option 1. Health data warrants defence-in-depth. DB constraint is a one-liner migration.

## Technical Details

**Affected files:**
- `backend/app/models/period.py` — `PeriodLogCreate` and `PeriodLogUpdate`
- New migration file: `backend/migrations/add_period_log_notes_constraint.sql`

## Acceptance Criteria

- [ ] `PeriodLogCreate.notes` has `max_length=1000`
- [ ] `PeriodLogUpdate.notes` has `max_length=1000`
- [ ] DB has CHECK constraint `char_length(notes) <= 1000`
- [ ] API returns 422 for notes exceeding 1000 chars

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified unbounded notes field
- Assessed prompt injection risk for future LLM features
