---
paths: [backend/app/repositories/**/*.py]
---

# Repository Rules

Repositories handle all Supabase queries. Nothing else touches the database.

## Must

- Take `AsyncClient` in `__init__`
- Return typed Pydantic models — never raw dicts or tuples
- Filter by `user_id` on every user-data query (RLS enforcement in code as well as DB)
- Raise `EntityNotFoundError` when data is not found
- Raise `DatabaseError` when queries fail
- Re-raise `EntityNotFoundError` before the generic `except` catches it

## Must Not

- Raise `HTTPException` — domain exceptions only
- Contain business logic
- Call external APIs

## Standard Query Pattern

Every repository method follows this shape:

```python
async def get(self, entity_id: str, user_id: str) -> EntityModel:
    try:
        response = (
            await self.client.table("entities")
            .select("*")
            .eq("id", entity_id)
            .eq("user_id", user_id)  # Always filter by user_id
            .execute()
        )
        if not response.data:
            raise EntityNotFoundError(f"Entity {entity_id} not found")
        return EntityModel(**response.data[0])
    except EntityNotFoundError:
        raise  # Re-raise before generic handler catches it
    except Exception as exc:
        logger.error("Failed to fetch entity: %s", exc, exc_info=True)
        raise DatabaseError(f"Failed to fetch entity: {exc}") from exc
```

## Return Types

```python
# NO — caller guesses field order, no IDE help
async def get_context(self, user_id: str) -> tuple[str, int | None]: ...

# YES — named fields, IDE autocomplete, self-documenting
async def get_context(self, user_id: str) -> UserContext: ...
```

Define models in `backend/app/models/[entity].py`.

## Supabase Mocking in Tests

Use helpers from `tests/fixtures/supabase.py`. Do not manually chain
`.table().select().eq().execute()` mocks — the fluent API makes manual
chaining fragile.

```python
from tests.fixtures.supabase import setup_supabase_response, setup_supabase_error

setup_supabase_response(mock_client, data=[{"id": "123", "name": "Test"}])
setup_supabase_error(mock_client, "Connection failed")
```
