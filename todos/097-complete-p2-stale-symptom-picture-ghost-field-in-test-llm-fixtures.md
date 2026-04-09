---
status: pending
priority: p2
issue_id: "097"
tags: [code-review, testing, quality]
dependencies: []
---

# Remove stale `symptom_picture` ghost field from `test_llm.py` fixtures

## Problem Statement

`TestLLMServiceGenerateProviderSummaryContent._VALID_JSON` still contains a `"symptom_picture"` field that was removed from `ProviderSummaryResponse` in Phase 5. Tests pass only because `extra="ignore"` silently drops the field — not because the fixture reflects what the real LLM will return. This is a stale fixture that masks the real model contract and could mislead future maintainers.

A second ghost-field issue exists at line 564: the missing-required-field test uses `'{"symptom_picture": "S"}'` as the invalid payload. The intent (test that missing `opening` raises `DatabaseError`) is correct, but `symptom_picture` was removed two phases ago and appears as dead context.

## Findings

- `backend/tests/services/test_llm.py:504` — `_VALID_JSON` includes `"symptom_picture": "Logs show hot flashes."`. `ProviderSummaryResponse` has no `symptom_picture` field; `extra="ignore"` drops it silently. Tests pass for the wrong reason.
- `backend/tests/services/test_llm.py:564` — Invalid-payload fixture is `'{"symptom_picture": "S"}'`. `symptom_picture` is a ghost field. The payload tests that missing `opening` raises `DatabaseError`, which is valid, but uses a meaningless key to do it.
- Root cause: `_VALID_JSON` was not updated when `symptom_picture` was removed in Phase 5. This commit removed `closing` but did not clean the pre-existing ghost field.
- Both `symptom_picture` and `closing` are now absent from the model, so the fixture drift predates this review by one phase.

## Proposed Solutions

### Option 1: Clean both fixtures

**Approach:** Update `_VALID_JSON` to contain only `opening` and `key_patterns`. Update the invalid-payload fixture to use a key that is simply wrong, not a ghost field.

```python
# Line 504
_VALID_JSON = '{"opening": "Patient presents.", "key_patterns": "Co-occur with night sweats."}'

# Line 564
mock_provider.chat_completion.return_value = '{"key_patterns": "Only patterns, no opening."}'
```

**Pros:**

- Fixtures now exactly match what the real LLM is instructed to return
- Test intent is immediately clear
- No silent `extra="ignore"` masking

**Cons:** None

**Effort:** < 15 minutes

**Risk:** Low — tests still pass, intent is clearer

---

### Option 2: Add a `test_valid_json_has_no_extra_fields` assertion

**Approach:** Add a test that parses `_VALID_JSON` and asserts the resulting model has exactly the expected fields, catching future fixture drift.

**Pros:** Regression-proof
**Cons:** More code than the fix warrants; the real fix is just cleaning the fixture

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

Use Option 1. Two-line fix, no risk.

## Technical Details

**Affected files:**

- `backend/tests/services/test_llm.py:504` — `_VALID_JSON` fixture
- `backend/tests/services/test_llm.py:564` — invalid-payload fixture

**Related:** `extra="ignore"` on `ProviderSummaryResponse` masks this in production tests.

## Resources

- **Commit:** f4dc4b14 (this review)
- **Related model:** `backend/app/models/appointment.py` — `ProviderSummaryResponse`
- **Pattern:** Phase 5 removed `symptom_picture`; this phase removed `closing`; both fields still appear in this fixture

## Acceptance Criteria

- [ ] `_VALID_JSON` at line 504 contains only `opening` and `key_patterns`
- [ ] Invalid-payload fixture at line 564 does not reference `symptom_picture`
- [ ] All tests still pass (`uv run pytest tests/services/test_llm.py -v`)

## Work Log

### 2026-04-08 - Identified in code review

**By:** Claude Code (ce-review)

**Actions:**

- Flagged by both `kieran-python-reviewer` and `code-simplicity-reviewer`
- Root cause: Phase 5 removed `symptom_picture` but did not clean this fixture
- `extra="ignore"` masked the stale field from test failures
