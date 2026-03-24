---
status: complete
priority: p1
issue_id: "040"
tags: [code-review, security, backend, medications, pr-2]
dependencies: []
---

# SQL injection in `search_reference` ILIKE pattern

## Problem Statement

`MedicationRepository.search_reference` builds an ILIKE filter by directly interpolating the user-supplied `query` string into a PostgREST `or_()` expression. A crafted value can break out of the ILIKE term and inject additional filter conditions.

## Findings

- `backend/app/repositories/medication_repository.py` lines 59, 66, 77
- Pattern: `pattern = f"%{query}%"` then `.or_(f"brand_name.ilike.{pattern},generic_name.ilike.{pattern}")`
- The PostgREST `or_()` filter is a parsed expression, not parameterized — a value like `%,notes.eq.SECRETVALUE` can inject extra filter clauses
- `%` alone returns all rows, bypassing search limits (20 + 10)
- ILIKE wildcards `%` and `_` are not escaped before interpolation
- Route `search` param has no `max_length` (lines 33 in `routes/medications.py`)
- Identified by security-sentinel

## Proposed Solutions

### Option 1: Validate and escape the search input (Recommended)

1. Add `max_length=100` to the `Query()` declaration on the `search` parameter
2. Escape ILIKE special characters before interpolation:
   ```python
   import re
   def _escape_ilike(query: str) -> str:
       return re.sub(r'([%_\\])', r'\\\1', query)

   pattern = f"%{_escape_ilike(query)}%"
   ```
3. Add a whitelist regex on the `search` parameter: allow only alphanumeric, spaces, hyphens, dots

**Pros:** Minimal change, keeps ILIKE approach
**Effort:** Small
**Risk:** Low

### Option 2: Switch to full-text search with tsvector

Use `to_tsquery` with the existing GIN index instead of ILIKE. Note: the current GIN index is on `tsvector` of brand + generic names, which would also fix the index-not-used performance issue (todo 047).

**Pros:** Fixes injection AND the non-functional index together
**Effort:** Medium
**Risk:** Medium — changes search semantics (full-word vs substring)

## Recommended Action

Option 1 for immediate safety. Track Option 2 for a future search improvement.

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py` lines 59–81
- `backend/app/api/routes/medications.py` line 33

## Acceptance Criteria

- [ ] ILIKE special characters `%`, `_`, `\` are escaped before interpolation
- [ ] `search` query param has `max_length=100`
- [ ] `search_reference("%, notes.eq.secret")` returns empty list / no injection
- [ ] `search_reference("%")` does not return all rows

## Work Log

- 2026-03-18: Identified by security-sentinel in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready

## Resources

- PR #2: feat/mht-medication-tracking
- File: `backend/app/repositories/medication_repository.py`
