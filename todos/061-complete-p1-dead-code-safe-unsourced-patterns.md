---
status: complete
priority: p1
issue_id: "061"
tags: [code-review, dead-code, ask-meno, citations]
dependencies: []
---

# Dead code: `_SAFE_UNSOURCED_PATTERNS` unreferenced in citations.py

## Problem Statement

`CitationService._SAFE_UNSOURCED_PATTERNS` is defined as a class attribute but is never referenced anywhere in the codebase. It was part of the v1 claim-stripping logic that was removed in this PR. Leaving it implies a safety mechanism is still active when it isn't — misleading to future engineers.

## Findings

- `backend/app/services/citations.py:381–394` — tuple defined, zero callers
- Grepped the entire backend: no references to `_SAFE_UNSOURCED_PATTERNS` outside the definition
- Confirmed by: python-reviewer, code-simplicity-reviewer

## Proposed Solutions

### Option 1: Delete the constant (Recommended)

**Approach:** Remove lines 381–394.

**Pros:** Removes misleading dead code. Zero functional change.
**Cons:** None.
**Effort:** Trivial.
**Risk:** None.

## Recommended Action

Delete the constant.

## Acceptance Criteria

- [ ] `_SAFE_UNSOURCED_PATTERNS` removed from `citations.py`
- [ ] `grep -r _SAFE_UNSOURCED_PATTERNS backend/` returns no results
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by python-reviewer and code-simplicity-reviewer in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
