---
status: complete
priority: p2
issue_id: "130"
tags: [code-review, python, documentation, citations]
---

# Stale docstring in `CitationService.extract()` references deleted method

## Problem Statement

`backend/app/services/citations.py` lines 303–304 (approximately) contain a docstring that references the now-deleted `sanitize_and_renumber` method:

> "References beyond the available chunks are silently ignored (should be removed by `sanitize_and_renumber` first)."

`sanitize_and_renumber` was deleted in PR #25 as dead code. The docstring now refers to a function that no longer exists, creating a false impression of the pipeline for any developer reading it.

## Proposed Solution

Update the docstring to accurately describe how out-of-range indices are handled now:

> "References beyond the available chunks are silently ignored."

Or more precisely:

> "References beyond the available chunks are silently ignored. Out-of-range source indices are handled by bounds checking in `render_structured_response`."

**Effort:** Trivial  
**Risk:** None

## Acceptance Criteria

- [ ] `sanitize_and_renumber` does not appear anywhere in `citations.py` docstrings or comments
- [ ] The `extract()` docstring accurately describes current behavior

## Work Log

- 2026-04-15: Identified by PR #25 code review (architecture-strategist). Direct consequence of fallback pipeline deletion.
