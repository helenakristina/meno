---
status: pending
priority: p2
issue_id: "022"
tags: [code-review, backend, testing, security]
dependencies: []
---

# Add IDOR regression tests and missing security test coverage

## Problem Statement

The period log endpoints correctly enforce ownership via compound `.eq("id", ...).eq("user_id", ...)` filters, but there are no tests verifying this. A future refactor that accidentally drops the `user_id` filter would pass all existing tests while enabling IDOR. Security-relevant properties should have regression tests.

Additionally: no test for the `_get_journey_stage` failure path (which silently returns `False` for bleeding alerts), and no test for the invalid date param path.

## Findings

- `backend/tests/api/routes/test_period.py` — no IDOR scenario tests
- `backend/app/repositories/period_repository.py` — PATCH/DELETE use double eq filter (correct) but untested
- `backend/app/services/period.py:192-208` — `_get_journey_stage` failure returns `None` → `bleeding_alert=False` silently; medical boundary implication; no test
- Security sentinel flagged all three as test gaps

## Proposed Solutions

### Option 1: Add targeted security regression tests

Add to `test_period.py` (routes or service level):

1. `test_delete_log_when_wrong_user_then_returns_404` — user B cannot delete user A's log
2. `test_update_log_when_wrong_user_then_returns_404` — user B cannot patch user A's log
3. `test_create_log_when_journey_stage_unavailable_then_bleeding_alert_false` — DB failure in `_get_journey_stage` silently returns False (document the behaviour or raise)
4. `test_get_logs_when_invalid_start_date_then_returns_422` — once todo 012 is fixed

**Effort:** 1.5 hours

**Risk:** None (adding tests only)

## Recommended Action

Option 1. These are simple test additions that would catch regressions in security-critical code paths.

## Technical Details

**Affected files:**
- `backend/tests/api/routes/test_period.py` — add IDOR and invalid param tests
- `backend/tests/services/test_period_service.py` — add journey stage failure path test

## Acceptance Criteria

- [ ] Test verifies user B cannot delete user A's log (receives 404)
- [ ] Test verifies user B cannot patch user A's log (receives 404)
- [ ] Test documents `_get_journey_stage` failure → `bleeding_alert=False` behaviour
- [ ] Test verifies invalid date param returns 422 (after todo 012 fix)

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)
