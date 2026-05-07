---
paths:
  - backend/app/api/dependencies.py
---

# Dependency Injection Rules

This file is the only place in the entire codebase where concrete classes are
instantiated. If you are writing `SomeClass(arg=...)` anywhere other than here,
it is almost certainly a violation.

## The Rule

- Routes → receive services via `Depends()`
- Services → receive repos via constructor args, wired here
- Repos → receive `AsyncClient` via constructor args, wired here
- This file → the only place `SomeClass(arg=...)` appears

## Pattern

```python
# Correct: factory functions chain from the bottom up
def get_symptom_repo(
    client: AsyncClient = Depends(get_client),
) -> SymptomRepository:
    return SymptomRepository(client=client)

def get_llm_provider(
    client: AsyncOpenAI = Depends(get_openai_client),
) -> LLMProviderBase:
    return OpenAIProvider(client=client)

def get_symptom_service(
    repo: SymptomRepository = Depends(get_symptom_repo),
    llm: LLMProviderBase = Depends(get_llm_provider),
) -> SymptomService:
    return SymptomService(repo=repo, llm_provider=llm)
```

## Before Adding a New Route

1. Add the repository factory function here first
2. Add the service factory function here
3. Then write the route using `Depends(get_your_service)`

Never write a route that receives a raw client or repository directly.
If a route needs a repository, that is a signal the logic belongs in a service.

## Test Overrides

In tests, override dependencies with `app.dependency_overrides`:

```python
app.dependency_overrides[get_symptom_service] = lambda: mock_service
```

Never patch concrete implementations in route tests — override at the factory level.
