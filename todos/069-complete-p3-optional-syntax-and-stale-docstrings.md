---
status: complete
priority: p3
issue_id: "069"
tags: [code-review, code-quality, python, ask-meno]
dependencies: []
---

# Minor Python quality issues: Optional syntax, type annotations, docstrings

## Problem Statement

Several small code quality issues in the PR's changed files, all easily fixed in one pass.

## Findings

1. **`medication_service` parameter has no type annotation** — `ask_meno.py:65`: `medication_service=None` — implicit `Any`. Should be `MedicationService | None = None` (using TYPE_CHECKING guard if needed).

2. **`Optional[...]` instead of `X | None`** — `ask_meno.py:18,64,75,134–136`: Project convention is modern `X | None` syntax. `Optional[PeriodRepository]`, `Optional[dict]`, `Optional[bool]` should all use `|`.

3. **Stale docstring in `prompts.py`** — `backend/app/services/prompts.py:31`: "Assemble the four-layer system prompt" — now five layers.

4. **Stale comment in `ask_meno.py`** — `:246`: "lower temperature for source faithfulness" — temperature was raised to 0.5 (also tracked in todo 064).

5. **`frozenset` missing type parameter** — `citations.py:56`: `_STOPWORDS: frozenset = frozenset(...)` should be `frozenset[str]`.

6. **Redundant except clause** — `ask_meno.py:298`: `except (json.JSONDecodeError, ValidationError, Exception)` — `Exception` is the base class of both; the first two are redundant. Write `except Exception as exc:` or split with specific handlers.

- Confirmed by: python-reviewer

## Proposed Solutions

Fix all in one pass while addressing other P1/P2 todos.

## Acceptance Criteria

- [ ] `medication_service: MedicationService | None = None` with type annotation
- [ ] All `Optional[X]` → `X | None` in changed files
- [ ] `prompts.py` docstring updated to "five-layer"
- [ ] `frozenset[str]` type annotation on `_STOPWORDS`
- [ ] Redundant except clause simplified
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by python-reviewer in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
