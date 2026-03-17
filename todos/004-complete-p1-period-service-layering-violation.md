---
status: pending
priority: p1
issue_id: "004"
tags: [code-review, backend, architecture, layering]
dependencies: []
---

# Fix `_get_journey_stage` — service accesses DB directly through `period_repo.client`

## Problem Statement

`PeriodService._get_journey_stage` bypasses the repository layer entirely by calling `self.period_repo.client.table("users").select("journey_stage")...` directly. This violates the project's strict layering rule (services must not touch `client`) and causes a silent failure bug: if the DB query errors, the method catches the exception and returns `None`, making `check_postmenopausal_bleeding_alert` return `False` for post-menopausal users — a medical boundary failure.

## Findings

- `backend/app/services/period.py:192-208` — raw `self.period_repo.client.table("users")` in a service method
- `UserRepository` already has `get_user_settings()` which returns `journey_stage`
- Silent failure: exception is caught and `None` returned, making `bleeding_alert` silently wrong for post-menopausal users
- The method is untestable via standard mocks — tests must mock `period_repo.client.table(...)...execute()`
- Confirmed by architecture reviewer, Python reviewer, and security sentinel

## Proposed Solutions

### Option 1: Inject `UserRepository` into `PeriodService`

**Approach:**
1. Add `user_repo: UserRepository` parameter to `PeriodService.__init__`
2. Replace `_get_journey_stage` body with `return await self.user_repo.get_user_settings(user_id)` (`.journey_stage`)
3. Update `get_period_service()` in `dependencies.py` to inject `get_user_repo()`

```python
# period.py
def __init__(self, period_repo: PeriodRepository, user_repo: UserRepository):
    self.period_repo = period_repo
    self.user_repo = user_repo

async def _get_journey_stage(self, user_id: str) -> str | None:
    try:
        settings = await self.user_repo.get_user_settings(user_id)
        return settings.journey_stage
    except EntityNotFoundError:
        return None
```

**Pros:** Correct layering, testable via mock, proper domain exception handling

**Cons:** Small DI change required

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Pass `journey_stage` as parameter from route

**Approach:** Have the route resolve `journey_stage` from `CurrentUser` or settings and pass it into `create_log(...)` as a parameter, eliminating the private method entirely.

**Pros:** Simplest — no new injection

**Cons:** Pushes data fetch responsibility to the route layer, route becomes thicker

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1. Injecting `UserRepository` follows the established DI pattern in this project and keeps the service self-contained.

## Technical Details

**Affected files:**
- `backend/app/services/period.py:192-208` — `_get_journey_stage` method
- `backend/app/services/period.py:__init__` — add `user_repo` parameter
- `backend/app/api/dependencies.py` — update `get_period_service` to pass `user_repo`

## Acceptance Criteria

- [ ] `PeriodService` no longer accesses `period_repo.client` directly
- [ ] `_get_journey_stage` uses `UserRepository` or receives `journey_stage` as a parameter
- [ ] `get_period_service` in `dependencies.py` injects `UserRepository`
- [ ] Tests mock `user_repo.get_user_settings` not `period_repo.client.table(...)`
- [ ] DB error in journey stage lookup raises domain exception, not returns `None` silently

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Identified direct DB access in service layer
- Traced silent failure path to bleeding_alert medical boundary bug
- Confirmed fix path via UserRepository injection
