---
paths: [backend/app/services/**/*.py]
---

# Service Rules

Services contain business logic. They orchestrate repositories and providers.
They never touch the database directly and never raise HTTPException.

## Must

- Accept all dependencies in `__init__` — never create them
- Use injected repositories for data access
- Use injected providers for external API calls (OpenAI, Anthropic)
- Raise domain exceptions (`ValidationError`, `DatabaseError`, `EntityNotFoundError`)
- Have complete type hints on all signatures
- Use Google-style docstrings only when they add information the code doesn't convey

## Must Not

- Import or instantiate `AsyncOpenAI`, `AsyncClient`, or any concrete client
- Raise `HTTPException` — that is the route's job
- Access `settings` directly for API keys — receive via DI
- Call Supabase directly — that is the repository's job

## The __init__ Rule

If `__init__` contains `SomeClass(arg=...)` on the right side of `=`, it is almost
certainly a violation. Dependencies arrive as arguments — they are not created here.

```python
# YES — receives dependencies
class SymptomService:
    def __init__(
        self,
        symptom_repo: SymptomRepository,
        llm_provider: LLMProviderBase,  # ABC, not a concrete class
    ) -> None:
        self._repo = symptom_repo
        self._llm = llm_provider

# NO — creates its own dependencies (violation)
class SymptomService:
    def __init__(self) -> None:
        self._repo = SymptomRepository(client=get_supabase_client())  # violation
        self._llm = OpenAIProvider(api_key=settings.OPENAI_API_KEY)   # violation
```

## Retry Decorator

All external API calls must use `@retry_transient`:

```python
from app.utils.retry import retry_transient

@retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
async def chat_completion(self, ...) -> str: ...
```

Retries: timeouts, rate limits (429), connection errors.
Does not retry: auth errors (401), not found (404), bad request (400).
Do not apply to: database queries, local functions, auth checks.
