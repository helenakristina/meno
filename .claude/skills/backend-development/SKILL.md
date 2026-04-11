`---
name: backend-development
description: >
Use when writing, modifying, or reviewing any backend code (FastAPI routes,
services, repositories, utilities, tests). Enforces this project's architectural
patterns: dependency injection via ABCs, repository pattern with domain exceptions,
thin routes, safe logging, and resilience patterns.
when_to_use: >
Any backend task: new features, bug fixes, refactoring, code review, or test writing
in the backend/ directory.
version: 1.0.0
languages: [python]

---

# Backend Development

## Architecture Overview

This is a FastAPI backend with Supabase (Postgres/pgvector), OpenAI integration,
and a health/menopause domain. It handles sensitive medical data.

```
Routes (thin)  →  Services (orchestration)  →  Repositories (data access)
                       ↓
                  Providers (external APIs via ABC)
                       ↓
                  Utils (pure functions, no side effects)
```

Every layer has one job. Don't mix them.

---

## Layer Rules

### Routes — Thin & Focused

Routes do orchestration only. 20-40 lines maximum.

**Routes MUST:**

- Accept request, call services, return response
- Validate input via Pydantic models
- Inject all dependencies via FastAPI `Depends()`
- Use `CurrentUser` dependency for auth
- Return proper status codes (201 create, 204 delete)
- Catch domain exceptions and convert to HTTPException

**Routes MUST NOT:**

- Contain business logic
- Call repositories directly — routes talk to services, never repositories
- Instantiate services or repositories (that's `dependencies.py`)
- Exceed 40 lines

```python
# YES — route calls the service; the service calls the repo
@router.post("/api/items", status_code=201, response_model=ItemResponse)
async def create_item(
    payload: CreateItemRequest,
    user: User = Depends(get_current_user),
    item_service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    """Create a new item."""
    return await item_service.create(user_id=user.id, payload=payload)


# NO — route is calling the repository directly (violation)
@router.post("/api/items", status_code=201, response_model=ItemResponse)
async def create_item(
    payload: CreateItemRequest,
    user: User = Depends(get_current_user),
    item_repo: ItemRepository = Depends(get_item_repo),  # ← violation
) -> ItemResponse:
    item = await item_repo.create(user.id, payload)  # ← repo called from route
    return ItemResponse(**item.model_dump())
```

The route's only job is to hand off to the service and return the result.
If a route needs a repository, that's a signal the logic belongs in a service.

### Services — Business Logic & Orchestration

Services contain business logic. They call repositories and providers but never
access the database directly.

**Services MUST:**

- Take dependencies in `__init__` (never create them)
- Use injected repositories for data access
- Use injected providers for external API calls
- Contain business logic, prompt building, data transformation
- Raise domain exceptions (`ValidationError`, etc.) — never `HTTPException`
- Have complete type hints and Google-style docstrings

**Services MUST NOT:**

- Import or instantiate `AsyncClient`, `AsyncOpenAI`, or any concrete client
- Raise `HTTPException` (that's the route's job)
- Access `settings` directly for API keys (receive via DI)
- Call Supabase directly (that's the repository's job)

```python
# YES — service receives its dependencies, never builds them
class ItemService:
    def __init__(
        self,
        item_repo: ItemRepository,
        llm_provider: LLMProviderBase,  # ABC, not a concrete class
    ) -> None:
        self._repo = item_repo
        self._llm = llm_provider

    async def create(self, user_id: str, payload: CreateItemRequest) -> ItemResponse:
        """Validate, enrich, and persist a new item.

        Args:
            user_id: Authenticated user's ID.
            payload: Validated request data.

        Returns:
            The created item.

        Raises:
            ValidationError: If business rules are violated.
            DatabaseError: If persistence fails.
        """
        if not payload.name.strip():
            raise ValidationError("Item name cannot be blank")

        item = await self._repo.create(user_id=user_id, data=payload)
        return ItemResponse(**item.model_dump())


# NO — service instantiating its own dependencies (violation)
class ItemService:
    def __init__(self) -> None:
        self._repo = ItemRepository(client=get_supabase_client())  # ← violation
        self._llm = OpenAIProvider(api_key=settings.OPENAI_API_KEY)  # ← violation
```

**The `__init__` rule in plain English:** if you see `=` followed by a class
instantiation inside `__init__`, it's almost certainly a violation. Dependencies
arrive as arguments — they don't get created here.

### Repositories — Data Access Only

Repositories handle all Supabase queries. Nothing else touches the database.

**Repositories MUST:**

- Take `AsyncClient` in `__init__`
- Return typed Pydantic models (never raw dicts or tuples)
- Filter by `user_id` on every query (RLS enforcement)
- Raise `EntityNotFoundError` when data not found
- Raise `DatabaseError` when queries fail
- Re-raise `EntityNotFoundError` before the generic `except` catches it

**Repositories MUST NOT:**

- Raise `HTTPException` (domain exceptions only)
- Contain business logic
- Call external APIs

```python
# Domain exception pattern — every repository method follows this shape
async def get(self, entity_id: str, user_id: str) -> EntityModel:
    try:
        response = (
            await self.client.table("entities")
            .select("*")
            .eq("id", entity_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not response.data:
            raise EntityNotFoundError(f"Entity {entity_id} not found")
        return EntityModel(**response.data[0])
    except EntityNotFoundError:
        raise  # Don't let the generic handler swallow this
    except Exception as exc:
        logger.error("Failed to fetch entity: %s", exc, exc_info=True)
        raise DatabaseError(f"Failed to fetch entity: {exc}") from exc
```

### Providers — External API Abstraction

Providers wrap external services (OpenAI, future Anthropic, etc.) behind ABCs.

**The three-file pattern:**

| File                 | Purpose                                                   |
| -------------------- | --------------------------------------------------------- |
| `[name]_base.py`     | ABC defining the interface contract                       |
| `[name]_provider.py` | Concrete implementation with real API calls               |
| `[name].py`          | Service that accepts the ABC, doesn't know which provider |

This is mandatory for all external API integrations. The service never knows
which provider it's using. Swapping providers means changing one line in
`dependencies.py`.

### Utils — Pure Functions

Utils are pure functions with no side effects, no database access, no API calls.

**Put logic here when:** it's a calculation, transformation, or formatting task
that could be reused across services, background jobs, CLI scripts, or exports.

Utils are the easiest code to test — no mocks needed, just input → output.

**The mock test:** if you could test this function with no mocks — just
input → output — it belongs in utils. If it needs a mock, it belongs
in a service or repository.

**Belongs in utils:** date calculations, stat formatting, text sanitization,
token counting, PII hashing, unit conversions.

**Does NOT belong in utils:** anything that calls `self._repo`, `self._llm`,
or touches `AsyncClient`. That's a service or repository.

---

## Dependency Injection Wiring

**IMPORTANT: Routes NEVER instantiate repositories or services directly. No exceptions.**

All DI wiring lives in `backend/app/api/dependencies.py`. This is the only place
where concrete implementations are instantiated. Routes receive dependencies via
`Depends()` — they never construct anything themselves.

### The rule in plain English

- Routes → call services (injected via `Depends`)
- Services → call repositories (injected via constructor, wired in `dependencies.py`)
- Repositories → call Supabase (injected via constructor, wired in `dependencies.py`)
- `dependencies.py` → the ONLY place `SomeClass(arg=...)` appears

### Correct pattern

```python
# dependencies.py — concrete classes are instantiated HERE and only here
def get_symptom_repo(client: AsyncClient = Depends(get_client)) -> SymptomRepository:
    return SymptomRepository(client=client)

def get_symptom_service(
    repo: SymptomRepository = Depends(get_symptom_repo),
) -> SymptomService:
    return SymptomService(repo=repo)

# routes/symptoms.py — routes receive dependencies, never build them
@router.get("/symptoms")
async def get_symptoms(
    service: SymptomService = Depends(get_symptom_service),
    user: User = Depends(get_current_user),
) -> list[SymptomResponse]:
    return await service.get_symptoms(user_id=user.id)
```

### What a violation looks like — NEVER do this

```python
# ❌ WRONG — repository instantiated directly in a route
@router.get("/symptoms")
async def get_symptoms(client: AsyncClient = Depends(get_client)):
    repo = SymptomRepository(client=client)  # ← violation
    return await repo.get_symptoms()

# ❌ WRONG — service instantiated directly in a route
@router.post("/symptoms")
async def log_symptom(data: SymptomCreate):
    service = SymptomService(repo=SymptomRepository(...))  # ← violation
    return await service.create(data)
```

When creating a new service or repository, always add its factory function to
`dependencies.py` before writing the route.

## Domain Exceptions

This project uses domain exceptions, not HTTPException, in services and repositories.
Routes catch domain exceptions and convert them to HTTP responses. Global exception
handlers in the app also catch them as a safety net.

| Exception             | Meaning                               | Typical HTTP mapping |
| --------------------- | ------------------------------------- | -------------------- |
| `EntityNotFoundError` | Data not found or user doesn't own it | 404                  |
| `DatabaseError`       | Supabase query failed                 | 500                  |
| `ValidationError`     | Business rule violation               | 400/422              |

Never raise `HTTPException` outside of route files.

---

## Pydantic Models

**Return Pydantic models from repositories, not dicts or tuples.**

```python
# NO — caller has to guess field order
async def get_context(self, user_id: str) -> tuple[str, int | None]:
    return journey_stage, age

# YES — caller uses named fields, IDE autocomplete works
async def get_context(self, user_id: str) -> UserContext:
    return UserContext(journey_stage=journey_stage, age=age)
```

Define models in `backend/app/models/[entity].py`. Keep them focused — one model
per distinct data shape, not one god-model per entity.

---

## Safe Logging (CRITICAL — Health Data)

This application handles sensitive medical data. Logging rules are non-negotiable.

**NEVER log:**

- User IDs in plain text (use `hash_user_id()` from `app.utils.logging`)
- Prompt content or LLM responses (use `safe_len()` for size only)
- Symptom data, personal notes, or any medical information
- Any user-generated content

**ALWAYS use:**

- `hash_user_id(user_id)` when logging user operations
- `safe_len(content)` when logging content sizes
- `safe_summary(operation, status)` for operation logging

```python
# NO
logger.info("User %s asked: %s", user_id, prompt)

# YES
logger.info("Generating completion for user: %s", hash_user_id(user_id))
logger.debug("LLM request: system=%d chars, user=%d chars", safe_len(system), safe_len(user))
```

---

## Retry & Resilience

All external API calls (OpenAI, Supabase storage, any network-dependent operation)
must use the `@retry_transient` decorator from `app/utils/retry.py`.

```python
@retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
async def chat_completion(self, ...) -> str:
    ...
```

**Retries:** Timeouts, rate limits (429), connection errors.
**Does not retry:** Auth errors (401), not found (404), bad request (400).

Do not add retry to: database queries, local functions, validation, auth checks.

---

## Supabase Testing Helper

When mocking Supabase, use the helpers in `tests/fixtures/supabase.py` — do NOT
manually chain `.table().select().eq().execute` mocks. The fluent API makes manual
mocking fragile.

```python
from tests.fixtures.supabase import setup_supabase_response, setup_supabase_error

# This works regardless of query chain length or order
setup_supabase_response(mock_client, data=[{"id": "123", "name": "Test"}])
setup_supabase_error(mock_client, "Connection failed")
```

Available helpers: `setup_supabase_response()`, `setup_supabase_error()`,
`setup_supabase_not_found()`, and the `mock_supabase` fixture.

---

## New Feature Checklist

When building a new backend feature, create files in this order:

1. **Models** — Pydantic models in `app/models/[entity].py`
2. **Repository** — Data access in `app/repositories/[entity]_repository.py`
3. **Service** — Business logic in `app/services/[entity].py`
   - If wrapping an external API: ABC in `[name]_base.py`, concrete in `[name]_provider.py`
4. **Dependencies** — Factory functions in `app/api/dependencies.py`
5. **Routes** — Thin endpoints in `app/api/routes/[feature].py`
6. **Tests** — Following the testing-discipline skill

### Per-file checks:

- [ ] Type hints on all signatures
- [ ] Docstrings on all public methods
- [ ] Domain exceptions (not HTTPException) in repos/services
- [ ] Safe logging (no PII, use logging utilities)
- [ ] `user_id` filter on all repository queries
- [ ] Pydantic return types from repositories
- [ ] Dependencies injected, never instantiated locally
- [ ] `@retry_transient` on external API calls

---

## Testing

Follow the **testing-discipline** skill for all testing decisions. Key points
specific to this backend:

- **Repositories:** Use `setup_supabase_response()` helper, not manual mock chains
- **Services:** Mock the injected ABC (e.g., `AsyncMock(spec=LLMProvider)`), assert
  on outcomes not call arguments
- **Routes:** Use `httpx.AsyncClient` with the real app, mock services via dependency
  overrides
- **Utils:** No mocks — pure input/output testing
- **Every test** must have a `# CATCHES:` comment per the testing-discipline skill
  `
