---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, backend, architecture, layering]
dependencies: []
---

# Move `has_uterus=False → disable period tracking` rule out of `UserRepository`

## Problem Statement

`user_repository.update_settings()` contains a business rule: if `has_uterus=False` is submitted, it automatically also sets `period_tracking_enabled=False`. Business rules belong in a service layer, not in the data access layer. Repositories should execute what they are told — not make decisions.

This also means the rule is untested at the right layer: the route test passes because the Supabase mock returns a pre-cooked row; the rule itself is never actually exercised.

## Findings

- `backend/app/repositories/user_repository.py:258-268` — `if data.has_uterus is not None: ... if data.has_uterus is False: update_data["period_tracking_enabled"] = False`
- The test `test_update_has_uterus_false_disables_period_tracking` passes regardless because the mock returns a hardcoded response — the logic itself is untested
- Python reviewer flagged this as a business rule in the wrong layer

## Proposed Solutions

### Option 1: Move rule to route handler (quick fix)

**Approach:** In the `PATCH /api/users/settings` route, before calling `user_repo.update_settings(data)`, check if `data.has_uterus is False` and mutate the request model to also set `period_tracking_enabled=False`.

**Pros:** Simple, no new service needed, logic is visible

**Cons:** Route becomes slightly thicker; still not in a dedicated service

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Create `UserSettingsService`

**Approach:** Create a thin `UserSettingsService` that wraps the repository and enforces rules like the `has_uterus` coercion. Route calls the service; service calls the repo.

**Pros:** Proper layering, testable in isolation

**Cons:** New service file for simple logic — YAGNI until more rules exist

**Effort:** 1 hour

**Risk:** Low

## Recommended Action

Option 1 for now. Move the rule to the route handler. When there are 2-3 such rules, extract a `UserSettingsService`.

## Technical Details

**Affected files:**
- `backend/app/repositories/user_repository.py:258-268` — remove business rule from `update_settings`
- `backend/app/api/routes/users.py` — add pre-call coercion logic
- `backend/tests/api/routes/test_users.py` — update test to verify coercion happens at route level

## Acceptance Criteria

- [ ] `UserRepository.update_settings` applies no business logic — just writes what it receives
- [ ] `has_uterus=False` → `period_tracking_enabled=False` rule is enforced at route or service layer
- [ ] Test for this rule exercises the actual logic path (not just mock return value)

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified business rule in repository layer
- Confirmed test doesn't exercise the actual rule
