---
title: "Backend Phase 4: Type Safety & Interface Compliance Cleanup"
category: logic-errors
date: 2026-03-16
tags:
  - pydantic
  - type-safety
  - abc
  - repositories
  - refactoring
  - fastapi
  - v2-standards
components:
  - backend/app/services/llm_base.py
  - backend/app/repositories/user_repository.py
  - backend/app/models/users.py
  - backend/app/models/chat.py
  - backend/app/api/routes/chat.py
  - backend/app/api/routes/users.py
  - backend/app/services/ask_meno.py
  - backend/app/utils/dates.py
severity: medium
status: resolved
---

# Backend Phase 4: Type Safety & Interface Compliance Cleanup

## Problem

After Phase 1–3 refactoring (exception hierarchy, PII-safe logging, thick route extraction), several medium-priority V2 standards violations remained:

1. `LLMProvider` used `Protocol` instead of `ABC` — inconsistent with all other interfaces
2. `UserRepository` methods (`get_profile`, `update_profile`, `create`, `get`) returned raw `dict` instead of typed Pydantic models
3. `get_suggested_prompts` route and service returned bare `dict` instead of a typed response model
4. `_validate_date_of_birth` helper lived in `routes/users.py` as a route-file helper, but was a pure validation function with no HTTP context dependency
5. Routes accessing `user_repo` results used `.get("field")` dict access instead of attribute access

## Root Cause

Phase 1–3 addressed structural/architectural issues. These remaining issues were medium-priority polish items deferred to Phase 4: type annotation gaps in the repository layer, interface inconsistency (Protocol vs ABC), and a utility function that accumulated HTTP concern (`raise HTTPException`) preventing its relocation.

## Solution

### 1. Protocol → ABC in `llm_base.py`

```python
# BEFORE
from typing import Protocol

class LLMProvider(Protocol):
    async def chat_completion(self, ...) -> str: ...

# AFTER
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def chat_completion(self, ...) -> str:
        pass
```

**Why:** CLAUDE.md mandates ABC for all interfaces. Protocol is duck-typed (no enforcement at subclass definition time), while ABC raises `TypeError` at instantiation if abstract methods are not implemented.

### 2. `UserProfile` model + typed repository returns

Added `UserProfile` to `app/models/users.py` with all optional fields (to accommodate partial DB column sets in different query contexts):

```python
class UserProfile(BaseModel):
    id: str
    email: str
    date_of_birth: date | None = None
    journey_stage: str | None = None
    insurance_type: str | None = None
    insurance_plan_name: str | None = None
    onboarding_completed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Updated `UserRepository.get_profile()`, `update_profile()`, `create()`, `get()` to return `UserProfile(**response.data[0])` instead of `response.data[0]`.

### 3. Routes use attribute access

```python
# BEFORE
profile = await user_repo.get(user_id)
return InsurancePreference(
    insurance_type=profile.get("insurance_type"),
    insurance_plan_name=profile.get("insurance_plan_name"),
)

# AFTER
profile = await user_repo.get(user_id)
return InsurancePreference(
    insurance_type=profile.insurance_type,
    insurance_plan_name=profile.insurance_plan_name,
)
```

For the onboarding route, `UserResponse(**created)` (dict unpacking) becomes `UserResponse.model_validate(created)` (Pydantic model → Pydantic model, uses `from_attributes=True`).

### 4. `SuggestedPromptsResponse` typed model

```python
# models/chat.py
class SuggestedPromptsResponse(BaseModel):
    prompts: list[str]

# services/ask_meno.py
async def get_suggested_prompts(self, ...) -> SuggestedPromptsResponse:
    ...
    return SuggestedPromptsResponse(prompts=final_prompts)

# routes/chat.py
async def get_suggested_prompts(...) -> SuggestedPromptsResponse:
    ...
```

### 5. `validate_date_of_birth` moved to `utils/dates.py`

```python
# utils/dates.py
def validate_date_of_birth(dob: date) -> None:
    """Validate date of birth: must be past and user must be 18+."""
    today = date.today()
    if dob >= today:
        raise ValueError("date_of_birth must be in the past")
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise ValueError("User must be at least 18 years old")

# routes/users.py — catch ValueError, convert to HTTPException
try:
    validate_date_of_birth(payload.date_of_birth)
except ValueError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
```

The key: the util raises `ValueError` (domain concern); the route converts to `HTTPException` (HTTP concern). This follows the same pattern as all other domain→HTTP exception conversions in the codebase.

## Test Updates Required

Changing repository return types from `dict` to `UserProfile` broke existing tests that used dict equality and dict access. Updates needed:

- `test_user_repository.py`: Change `assert result == user_data` → `assert isinstance(result, UserProfile)` and `result["field"]` → `result.field`
- `test_users.py` (route tests): Mock data missing `id`/`email` fields caused `ValidationError` on `UserProfile` construction — add required fields to mock rows
- `test_ask_meno_service.py`: Change `result["prompts"]` → `result.prompts` and `"prompts" in result` → check `result.prompts` directly

## Prevention

- **Repository contract rule**: All repository methods must return typed Pydantic models, never raw `dict`. The return type annotation (`-> UserProfile`) enforces this at the type checker level.
- **Interface rule**: CLAUDE.md mandates ABC for all interfaces. When adding a new provider/service interface, reach for ABC immediately.
- **Route response rule**: All FastAPI route handlers should declare `response_model=` and return a typed Pydantic model, not `dict`. This ensures OpenAPI docs are accurate and type checking works end-to-end.
- **Helper placement rule**: If a function raises `ValueError` (or other domain exceptions), it belongs in `utils/`. If it raises `HTTPException`, it must stay in a route handler or be refactored to raise domain exceptions first.
- **Test mock completeness**: When mock DB rows are used for repository tests, include all required Pydantic model fields, not just the fields being tested. This prevents silent failures when models gain required fields.

## Result

- 733 tests passing (up from 675 before this session's earlier work)
- 84% coverage maintained
- 0 `Protocol` usages in `app/services/`
- 0 `-> dict` return types in `app/api/routes/` or `app/repositories/`
