---
paths: [backend/app/providers/**/*.py]
---

# Provider Rules

Providers wrap external services (OpenAI, Anthropic, future APIs) behind ABCs.
Services depend on the ABC — they never know which concrete provider they are using.

## Three-File Pattern (Mandatory)

| File | Purpose |
|---|---|
| `[name]_base.py` | ABC defining the interface contract |
| `[name]_provider.py` | Concrete implementation with real API calls |
| `[name].py` | (or the service itself) accepts the ABC |

Swapping providers = changing one line in `dependencies.py`. Nothing else changes.

## ABC Rules

- Define every method the service needs as `@abstractmethod`
- Return types must be concrete (Pydantic models or primitives) — not provider-specific types
- No implementation logic in the ABC

```python
# app/providers/llm_base.py
from abc import ABC, abstractmethod

class LLMProviderBase(ABC):
    @abstractmethod
    async def chat_completion(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> str: ...

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]: ...
```

## Concrete Provider Rules

- Apply `@retry_transient` on every external API call
- Catch provider-specific exceptions and re-raise as domain exceptions
- Never leak provider SDK types into return values
- Log with `safe_len()` only — never log prompt content or response content

```python
# app/providers/openai_provider.py
class OpenAIProvider(LLMProviderBase):
    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def chat_completion(self, system: str, user: str, max_tokens: int = 1000) -> str:
        logger.debug("LLM request: system=%d chars, user=%d chars", safe_len(system), safe_len(user))
        response = await self._client.chat.completions.create(...)
        return response.choices[0].message.content
```
