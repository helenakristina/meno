---
paths: [backend/tests/**/*.py]
---

# Backend Test Rules

## Mock Only What You Don't Own

```
External services (Supabase, OpenAI) → mock at the boundary
Your own services and functions    → use the real thing
```

## What to Test at Each Layer

**Routes:** Use `httpx.AsyncClient` with the real FastAPI app. Override dependencies
via `app.dependency_overrides`. Test status codes, response shapes, auth failures,
bad input — not just happy paths.

```python
# CATCHES: Endpoint returns 200 when auth is missing instead of 401
async def test_create_symptom_requires_auth(client: httpx.AsyncClient):
    response = await client.post("/api/symptoms", json={...})
    assert response.status_code == 401
```

**Services:** Call the real service. Mock only injected ABCs (e.g.,
`AsyncMock(spec=LLMProviderBase)`). Assert on return values and raised exceptions,
not on internal call arguments.

**Repositories:** Use `setup_supabase_response()` / `setup_supabase_error()` from
`tests/fixtures/supabase.py`. Never manually chain `.table().select().eq().execute()`
mocks — they are fragile and break on any query reorder.

```python
from tests.fixtures.supabase import setup_supabase_response, setup_supabase_error

setup_supabase_response(mock_client, data=[{"id": "123"}])
setup_supabase_error(mock_client, "Connection failed")
```

**Utils:** No mocks. Pure input → output.

## RAG / pgvector Tests — Not Optional

```python
# CATCHES: ORDER BY similarity DESC accidentally becomes ASC during refactor
async def test_similarity_search_returns_results_in_score_order(mock_supabase):
    chunks = [
        {"id": "a", "similarity": 0.92},
        {"id": "b", "similarity": 0.75},
        {"id": "c", "similarity": 0.61},
    ]
    setup_supabase_response(mock_supabase, data=chunks)
    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=3)
    assert [r.id for r in results] == ["a", "b", "c"]

# CATCHES: top_k parameter ignored — all chunks returned, blowing context window
async def test_similarity_search_respects_top_k(mock_supabase):
    chunks = [{"id": str(i), "similarity": 0.9 - i * 0.01} for i in range(20)]
    setup_supabase_response(mock_supabase, data=chunks)
    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=5)
    assert len(results) == 5

# CATCHES: Empty result raises IndexError instead of returning []
async def test_similarity_search_returns_empty_list_when_no_results(mock_supabase):
    setup_supabase_response(mock_supabase, data=[])
    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=5)
    assert results == []
```

## Anti-Patterns

| Pattern                                   | Problem                                 | Instead                                 |
| ----------------------------------------- | --------------------------------------- | --------------------------------------- |
| Mocking your own service classes          | Tests prove nothing about real behavior | Call real service with mocked externals |
| `assert mock.called_with(...)` only       | Tests the call, not the result          | Assert on return value or side effect   |
| Fixtures duplicating implementation logic | Test is tautological                    | Use simple, static test data            |
| Only happy path per endpoint              | Misses auth, validation, edge cases     | Test failures, bad input, missing auth  |
