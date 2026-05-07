---
name: add-provider
description: >
  Procedure for adding a new external API provider using the three-file ABC pattern.
  Use when integrating a new external service (LLM, embeddings, email, storage, etc.)
  or when swapping an existing provider implementation.
---

# Add Provider

Use this when wrapping a new external service. The three-file pattern ensures
services never depend on a concrete provider — swapping providers means one line
in `dependencies.py`.

## The Three Files

```
backend/app/providers/
├── [name]_base.py        ← ABC (interface contract)
├── [name]_provider.py    ← Concrete implementation
└── (the service accepts the ABC — it does not live here)
```

## Step 1: Define the ABC (`[name]_base.py`)

```python
from abc import ABC, abstractmethod

class [Name]ProviderBase(ABC):
    """Abstract interface for [Name] operations."""

    @abstractmethod
    async def [method_one](self, ...) -> ReturnType: ...

    @abstractmethod
    async def [method_two](self, ...) -> ReturnType: ...
```

Rules for the ABC:
- Every method the service needs must be `@abstractmethod`
- Return types must be your domain types, not provider SDK types
- No implementation logic here
- Docstring on the class, not on each abstract method (the implementation documents behavior)

## Step 2: Write the Test Against the ABC

Before implementing the concrete provider, write a failing test for the service
that depends on it. Mock the ABC:

```python
# CATCHES: Service passes raw user text to provider instead of anonymized version
async def test_service_anonymizes_before_provider_call():
    mock_provider = AsyncMock(spec=[Name]ProviderBase)
    mock_provider.[method_one].return_value = expected_result
    service = [Domain]Service(provider=mock_provider)

    await service.do_thing(user_id="user-abc", content="personal note")

    call_args = mock_provider.[method_one].call_args
    assert "personal note" not in str(call_args)
```

## Step 3: Implement the Concrete Provider (`[name]_provider.py`)

```python
from app.utils.logging import safe_len
from app.utils.retry import retry_transient
from app.providers.[name]_base import [Name]ProviderBase

class [Name]Provider([Name]ProviderBase):
    def __init__(self, client: [SDKClient]) -> None:
        self._client = client

    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def [method_one](self, ...) -> ReturnType:
        logger.debug("[method_one]: input=%d chars", safe_len(input))
        try:
            result = await self._client.[sdk_method](...)
            return YourDomainType(...)  # Never return raw SDK types
        except [ProviderSpecificError] as exc:
            raise DatabaseError(f"[Name] call failed: {exc}") from exc
```

Rules for the concrete provider:
- `@retry_transient` on every external API call
- Catch provider-specific exceptions, re-raise as domain exceptions
- Never return raw SDK types — always map to your domain types
- Log input size with `safe_len()` — never log content

## Step 4: Wire in `dependencies.py`

```python
def get_[name]_client() -> [SDKClient]:
    return [SDKClient](api_key=settings.[NAME]_API_KEY)

def get_[name]_provider(
    client: [SDKClient] = Depends(get_[name]_client),
) -> [Name]ProviderBase:  # Return the ABC, not the concrete type
    return [Name]Provider(client=client)

def get_[domain]_service(
    provider: [Name]ProviderBase = Depends(get_[name]_provider),
) -> [Domain]Service:
    return [Domain]Service(provider=provider)
```

## Swapping Providers Later

Change one line in `dependencies.py`:
```python
# Was: return [Name]Provider(client=client)
return [AlternateName]Provider(client=alternate_client)
```

The service and tests are unchanged.
