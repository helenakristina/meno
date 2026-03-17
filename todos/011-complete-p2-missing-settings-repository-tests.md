---
status: pending
priority: p2
issue_id: "011"
tags: [code-review, backend, testing]
dependencies: [010]
---

# Add repository-layer tests for `get_settings` and `update_settings`

## Problem Statement

`test_user_repository.py` has 24 test functions but none cover the two new `get_settings` and `update_settings` methods added in this branch. The business logic in `update_settings` (the `has_uterus=False` coercion) is only covered by an end-to-end route test that relies on a hardcoded mock response — the actual repository logic is never directly tested.

## Findings

- `backend/tests/repositories/test_user_repository.py` — no tests for `get_settings` or `update_settings`
- Route tests cover happy path end-to-end via mock responses
- The `has_uterus=False → disable period tracking` coercion (currently in the repo, moving to route per todo 010) needs a direct test wherever it lives
- Python reviewer flagged as "should fix"

## Proposed Solutions

### Option 1: Add 4 targeted repository tests

**Approach:** Add to `test_user_repository.py`:

1. `test_get_settings_when_user_found_then_returns_settings`
2. `test_get_settings_when_user_not_found_then_raises_entity_not_found`
3. `test_update_settings_when_valid_data_then_returns_updated_settings`
4. `test_update_settings_when_user_not_found_then_raises_entity_not_found`

Plus, once todo 010 is done: add test at the route/service layer verifying `has_uterus=False` coercion.

**Pros:** Direct coverage of the new code, follows existing `test_X_when_Y_then_Z` naming convention

**Effort:** 1 hour

**Risk:** Low

## Recommended Action

Option 1. Straightforward — follow the existing test patterns in the file.

## Technical Details

**Affected files:**
- `backend/tests/repositories/test_user_repository.py` — add 4 test functions

## Acceptance Criteria

- [ ] `test_get_settings_when_user_found_then_returns_settings` added and passing
- [ ] `test_get_settings_when_user_not_found_then_raises_entity_not_found` added and passing
- [ ] `test_update_settings_when_valid_data_then_returns_updated_settings` added and passing
- [ ] `test_update_settings_when_user_not_found_then_raises_entity_not_found` added and passing
- [ ] Test for `has_uterus=False` coercion at whichever layer it lives after todo 010

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Confirmed no repository-layer tests for new settings methods
- Identified coercion logic as having no direct test coverage
