---
status: pending
priority: p2
issue_id: "098"
tags: [code-review, testing, quality]
dependencies: []
---

# Add `test_no_closing_field` regression guard to `test_appointment_pdf_models.py`

## Problem Statement

The commit deleted `test_missing_closing_raises_validation_error` but did not add a `test_no_closing_field` regression guard in its place. The existing test `test_no_symptom_picture_field` establishes a pattern: for every field removed from `ProviderSummaryResponse`, there should be a test asserting that field is absent. Without this guard, `closing` could be silently re-introduced (e.g., by a future LLM prompt update that adds a third field) and no test would catch it before the PDF builder tries to render a section that no longer exists.

## Findings

- `backend/tests/models/test_appointment_pdf_models.py:32` — `test_no_symptom_picture_field` asserts `not hasattr(m, "symptom_picture")`. This is the established pattern for removed fields.
- No equivalent test exists for `closing` after this commit's deletion of `test_missing_closing_raises_validation_error`.
- The asymmetry means `symptom_picture` has a regression guard; `closing` does not.
- `extra="ignore"` makes this guard valuable: without it, `closing` would be silently ignored by Pydantic even if accidentally re-added.

## Proposed Solutions

### Option 1: Add `test_no_closing_field` mirroring the existing pattern

**Approach:** Add one test immediately after `test_no_symptom_picture_field`:

```python
def test_no_closing_field(self):
    # CATCHES: closing accidentally re-added — removed alongside "Next Steps"
    # PDF section; the PDF no longer renders a closing section
    m = ProviderSummaryResponse(opening="O")
    assert not hasattr(m, "closing")
```

**Pros:**

- Exactly matches the pattern established by `test_no_symptom_picture_field`
- Catches regression if `closing` is re-added to the model
- Zero maintenance burden

**Cons:** None

**Effort:** < 5 minutes

**Risk:** None

---

### Option 2: Combined guard for all removed fields

**Approach:** A single test asserts neither `symptom_picture` nor `closing` is present.

```python
def test_model_has_no_removed_fields(self):
    m = ProviderSummaryResponse(opening="O")
    assert not hasattr(m, "symptom_picture")
    assert not hasattr(m, "closing")
```

**Pros:** Single test covers all removed fields
**Cons:** Combines two unrelated removal phases; less readable than separate tests
**Effort:** < 5 minutes
**Risk:** None

## Recommended Action

Option 1 — one test per removed field, matching the existing pattern.

## Technical Details

**Affected files:**

- `backend/tests/models/test_appointment_pdf_models.py` — add after line 36 (after `test_no_symptom_picture_field`)

## Resources

- **Commit:** f4dc4b14 (this review)
- **Pattern reference:** `test_no_symptom_picture_field` at line 32

## Acceptance Criteria

- [ ] `test_no_closing_field` added to `TestProviderSummaryResponse`
- [ ] Test asserts `not hasattr(m, "closing")` on a valid `ProviderSummaryResponse` instance
- [ ] All tests pass (`uv run pytest tests/models/test_appointment_pdf_models.py -v`)

## Work Log

### 2026-04-08 - Identified in code review

**By:** Claude Code (ce-review)

**Actions:**

- Flagged by `kieran-python-reviewer` and `architecture-strategist`
- The pattern of `test_no_X_field` tests is established in this test class
- Simple 5-minute fix
