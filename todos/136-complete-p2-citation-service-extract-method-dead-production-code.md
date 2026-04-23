---
status: pending
priority: p2
issue_id: "136"
tags: [code-review, python, dead-code, citations, quality]
---

# `CitationService.extract()` is dead production code — zero callers in `app/`

## Problem Statement

`backend/app/services/citations.py` lines 298–349: `extract()` has no callers in production code. `grep -rn "\.extract(" backend/app/` returns nothing. The method is only called from `backend/tests/services/test_citations.py`.

This PR deleted 194 lines of the fallback citation pipeline. `extract()` is the surviving remnant of that same dead path. The PR description states the v2 structured response (`render_structured_response`) is "now the sole pipeline" — but `extract()` still exists alongside it.

**Consequences of leaving it:**

1. Future developers may believe a dual-path pipeline still exists
2. Tests covering dead code create false coverage confidence
3. The method's docstring references `render_structured_response` to explain its behavior — implicitly acknowledging it's disconnected from the live pipeline

## Proposed Solution

Delete `extract()` (lines 298–349) and all its test cases in `test_citations.py` (the `TestExtract` class and any calls to `.extract()`, ~13 test cases).

If `extract()` has a planned V2 use (e.g., future plain-text LLM fallback), document it in `docs/plans/` instead of keeping live dead code.

**Effort:** Small (delete ~52 lines from citations.py + ~80 lines from tests)  
**Risk:** None — no production path calls it

## Acceptance Criteria

- [ ] `CitationService.extract()` deleted from `citations.py`
- [ ] All `TestExtract` test cases deleted from `test_citations.py`
- [ ] All remaining tests still pass (1075+ tests, 0 failures)
- [ ] No remaining references to `.extract(` in `app/` or non-test code

## Work Log

- 2026-04-21: Identified by PR #25 code review (kieran-python-reviewer, architecture-strategist, code-simplicity-reviewer). Confirmed dead by `grep -rn ".extract(" backend/app/` returning empty.
