---
status: complete
priority: p3
issue_id: "057"
tags: [code-review, backend, testing, medications, pr-2]
dependencies: []
---

# Misleading test name `test_change_dose_returns_200` and `pytest.approx` misuse

## Problem Statement

Two test quality issues in the new medication test files: a test named `returns_200` that asserts `201`, and `pytest.approx` applied to a dict of strings where it provides no benefit.

## Findings

**Issue 1:** `backend/tests/api/routes/test_medications.py` line 317
- Test `test_change_dose_returns_200` asserts `status_code == 201`
- The test passes (assertion is correct) but the name is wrong
- Rename to `test_change_dose_returns_201`

**Issue 2:** `backend/tests/repositories/test_medication_repository.py` line 312
- `client.rpc.assert_called_once_with("change_medication_dose", pytest.approx({...}, abs=0))`
- `pytest.approx` is for floating-point comparisons — using it on a dict of strings and `None` with `abs=0` provides no tolerance benefit
- Replace with plain dict equality: `client.rpc.assert_called_once_with("change_medication_dose", {...})`

Identified by Python reviewer.

## Proposed Solutions

Fix both issues directly — no design trade-offs involved.

## Technical Details

**Affected files:**
- `backend/tests/api/routes/test_medications.py` line 317 — rename test
- `backend/tests/repositories/test_medication_repository.py` line 312 — remove `pytest.approx`

## Acceptance Criteria

- [ ] `test_change_dose_returns_200` renamed to `test_change_dose_returns_201`
- [ ] `pytest.approx` removed from the RPC call assertion
- [ ] All tests still pass

## Work Log

- 2026-03-18: Identified by Python reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
