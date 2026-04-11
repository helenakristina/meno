---
name: Ruff formatting fixes
status: complete
priority: p2
issue_id: 001
tags: [code-review, python, formatting]
dependencies: []
---

## Problem Statement

Several files in PR #14 need Ruff formatting fixes to match the project's code style.

## Findings

**From:** kieran-python-reviewer

**Files needing formatting:**

1. `backend/app/llm/appointment_prompts.py` - Line 291: Use double quotes instead of single quotes for f-string
2. `backend/app/services/appointment.py` - General formatting
3. `backend/app/services/llm.py` - General formatting
4. `backend/app/services/pdf.py` - General formatting

**Also:**

- `backend/app/services/appointment.py` line 15: Unused import `typing.Any`

## Proposed Solutions

### Option A: Run Ruff Format (Recommended)

**Effort:** Small

```bash
cd backend
uv run ruff check . --fix
uv run ruff format .
```

### Option B: Manual Fix

Remove unused import and fix quote style manually.

**Effort:** Small
**Risk:** Low

## Recommended Action

Run Option A (Ruff format) before merge.

## Technical Details

**Affected files:**

- `backend/app/services/appointment.py`
- `backend/app/services/llm.py`
- `backend/app/services/pdf.py`
- `backend/app/llm/appointment_prompts.py`

## Acceptance Criteria

- [ ] `uv run ruff check .` passes with no errors
- [ ] `uv run ruff format .` makes no changes
- [ ] Unused `typing.Any` import removed from appointment.py

## Work Log

| Date       | Action                   | Result  |
| ---------- | ------------------------ | ------- |
| 2026-03-31 | Created from code review | Pending |
