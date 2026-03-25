---
status: complete
priority: p3
issue_id: "070"
tags: [code-review, testing, citations, ask-meno]
dependencies: []
---

# Test quality gaps in new citation and model tests

## Problem Statement

Several test quality issues in the new test files introduced by this PR.

## Findings

1. **`test_false_positive_rejection_slash_prefix` asserts ambiguous behavior** — `test_citations.py:173–182`: The assertion has a comment "Might still be there if our regex allows it" — the test passes regardless of actual behavior. It should either be made precise or deleted.

2. **`test_no_disclaimer_when_none` fragile assertion** — `test_citations.py:554`: `assert rendered.strip().endswith("[Source 1]")` — breaks if body text ends with a period or if rendering changes trailing whitespace. The intent ("no disclaimer appended") should be asserted directly.

3. **Missing test: two sections referencing same out-of-range source_index** — `citations.py:436–461`: Logic for "already seen" and "valid range" is interleaved; only a single out-of-range section is tested. Should add a test with two sections sharing the same out-of-range index.

4. **Missing test: all sections empty, insufficient_sources=False, disclaimer=None** — `citations.py:472`: The fallback uses `structured.disclaimer or (hardcoded message)`. No test covers the branch where all bodies are whitespace and disclaimer is also None.

5. **Test naming convention** — `test_chat_models.py`, `test_prompts.py`: CLAUDE.md requires `test_X_when_Y_then_Z`. New tests use `test_body_is_required`, `test_v2_schema_in_prompt_not_v1`, etc.

6. **Duplicate fixtures** — `test_citations.py`: `sample_chunks` (lines 20–41) and `render_chunks` (lines 422–444) are structurally identical. Consolidate into one shared fixture.

- Confirmed by: python-reviewer, code-simplicity-reviewer

## Acceptance Criteria

- [ ] `test_false_positive_rejection_slash_prefix` fixed or deleted
- [ ] `test_no_disclaimer_when_none` asserts intent directly (not `endswith`)
- [ ] Test added: two sections same out-of-range source_index
- [ ] Test added: all bodies whitespace + disclaimer=None
- [ ] Test naming follows `test_X_when_Y_then_Z` in new test files
- [ ] `sample_chunks` and `render_chunks` fixtures consolidated

## Work Log

- 2026-03-23: Found by python-reviewer and code-simplicity-reviewer in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
