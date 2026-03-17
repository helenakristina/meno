---
title: "IDOR regression test pattern for double-eq ownership filters"
category: architecture-issues
date: 2026-03-17
tags: [security, testing, idor, repository, backend, fastapi]
---

# IDOR regression test pattern for ownership filters

## Problem

Period log endpoints (PATCH, DELETE) correctly applied `.eq("id", log_id).eq("user_id", user_id)` double filters to prevent one user from modifying another's data (IDOR — Insecure Direct Object Reference). However, **no tests verified this**. A future refactor that accidentally dropped the `user_id` filter would pass all existing tests while enabling IDOR.

## Root Cause

Route-level tests mock the service entirely, so they never exercise the repository's ownership logic. Without dedicated repository tests, the IDOR guard is present in code but not validated by the test suite.

## Solution

Add repository-layer tests that verify:
1. Both `.eq("id", ...)` and `.eq("user_id", ...)` are called during PATCH/DELETE
2. When the combined filter returns 0 rows (simulating a different user's log), `EntityNotFoundError` is raised

```python
# tests/repositories/test_period_repository.py

class TestUpdateLogOwnership:
    @pytest.mark.asyncio
    async def test_update_log_applies_user_id_filter(self):
        """update_log must call .eq('user_id', user_id) to prevent IDOR."""
        chain = make_chain(data=[row])
        repo = PeriodRepository(client=make_client(chain))
        await repo.update_log("owner-user", "log-1", data)

        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("log-1" in c for c in eq_calls), "Must filter by log id"
        assert any("owner-user" in c for c in eq_calls), "Must filter by user_id (IDOR guard)"

    @pytest.mark.asyncio
    async def test_update_log_returns_not_found_for_wrong_user(self):
        """Simulates IDOR attempt — wrong user gets EntityNotFoundError."""
        chain = make_chain(data=[])  # DB returns 0 rows (ownership filter blocked it)
        repo = PeriodRepository(client=make_client(chain))

        with pytest.raises(EntityNotFoundError):
            await repo.update_log("attacker-user", "log-1", data)
```

## Prevention

For any repository method that modifies or deletes data:
- Add a test that asserts the `user_id` filter is applied (check `chain.eq.call_args_list`)
- Add a test where the DB returns 0 rows (simulating ownership mismatch) and assert `EntityNotFoundError`
- Route-level tests alone are insufficient for IDOR coverage — they never reach the DB layer

## Files in this Codebase

- `backend/tests/repositories/test_period_repository.py` — full IDOR test suite
- `backend/app/repositories/period_repository.py` — double-eq pattern: `.eq("id", log_id).eq("user_id", user_id)`
