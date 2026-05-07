---
name: scaffold-feature
description: >
  End-to-end procedure for scaffolding a new Meno backend feature.
  Use when starting a new feature from scratch: creates models, repository,
  service, DI wiring, route, and tests in the correct order.
  Invoke with /scaffold-feature or when asked to build a new feature end-to-end.
---

# Scaffold Feature

This skill walks through creating a complete backend feature in the correct order.
Do not jump ahead. Each step depends on the previous one being complete.

## Pre-Flight

Before writing any code:

1. State which testing approach applies (TDD — this is new code)
2. Identify the domain entity (e.g., `MedicationLog`)
3. Confirm the layer build order below

## Build Order

### 1. Models (`backend/app/models/[entity].py`)

Define Pydantic models first. Everything else depends on these shapes.

- Request model (input validation)
- Response model (what the route returns)
- Domain model (what the repository returns internally)
- Keep models focused — one model per data shape, not one god-model

### 2. Repository (`backend/app/repositories/[entity]_repository.py`)

Write the failing test first. Then implement.

- Takes `AsyncClient` in `__init__`
- Filters by `user_id` on every query
- Returns Pydantic domain models
- Raises `EntityNotFoundError` / `DatabaseError`
- Re-raises `EntityNotFoundError` before the generic except

### 3. Service (`backend/app/services/[entity]_service.py`)

Write the failing test first. Then implement.

- Takes dependencies in `__init__` (repo, provider) — never creates them
- Contains business logic and orchestration
- Raises domain exceptions only
- Apply `@retry_transient` on any external API calls

If this feature wraps an external API, create the provider files first:
- `backend/app/providers/[name]_base.py` — ABC
- `backend/app/providers/[name]_provider.py` — concrete

### 4. DI Wiring (`backend/app/api/dependencies.py`)

Add factory functions before writing the route.

```python
def get_[entity]_repo(client: AsyncClient = Depends(get_client)) -> [Entity]Repository:
    return [Entity]Repository(client=client)

def get_[entity]_service(
    repo: [Entity]Repository = Depends(get_[entity]_repo),
) -> [Entity]Service:
    return [Entity]Service(repo=repo)
```

### 5. Route (`backend/app/api/routes/[feature].py`)

Write the failing test first (route test using `httpx.AsyncClient`). Then implement.

- Thin — accept, delegate to service, return
- All deps via `Depends()`
- Domain exceptions → `HTTPException`
- Max ~40 lines

### 6. Route Registration (`backend/app/main.py`)

Add `app.include_router(your_router, prefix="/api")`.

## Per-File Checklist

- [ ] Type hints on all signatures
- [ ] Domain exceptions in repos/services (not HTTPException)
- [ ] PII-safe logging (hash_user_id, safe_len)
- [ ] user_id filter on all repository queries
- [ ] Pydantic return types from repositories
- [ ] Dependencies injected, never instantiated locally
- [ ] @retry_transient on external API calls
- [ ] CATCHES comment on every test
