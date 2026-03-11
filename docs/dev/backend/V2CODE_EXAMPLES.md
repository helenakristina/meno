# V2 Code Examples & Patterns

**Purpose:** Reference examples for implementing V2 features with consistent quality, DI, and testing.

**When to use:** Copy patterns from here when writing new code. Reference these in Claude Code prompts.

---

## Part 1: Dependency Injection Pattern (For All Services)

### The Pattern

**Bad (Hardcoded Dependencies):**

```python
# ❌ Don't do this
async def generate_summary(frequency_stats):
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)  # Hardcoded!
    response = await client.chat.completions.create(...)
    return response.choices[0].message.content
```

**Good (Dependency Injection):**

```python
# ✅ Do this
class LLMService:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_summary(self, frequency_stats):
        return await self.provider.chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(frequency_stats),
            max_tokens=600,
            temperature=0.3,
        )
```

### Why DI Matters

1. **Testing:** Can inject mock provider instead of real OpenAI
2. **Flexibility:** Can swap providers (OpenAI → Claude) by changing one line
3. **Clarity:** Dependencies are explicit in `__init__`

### DI Template for V2 Services

**IMPORTANT: Three files, not two. Abstract interface + concrete implementation + service.**

**Step 1: Define Abstract Base Class (Interface)**

```python
# backend/app/services/[service_name]_base.py

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SomeDependency(ABC):
    """Abstract interface for dependency.

    Concrete implementations (e.g., ConcreteProvider, AnotherProvider)
    inherit from this and implement abstract methods.
    """

    @abstractmethod
    async def do_something(self, data: str) -> str:
        """Abstract method - subclasses must implement this.

        Args:
            data: Input data.

        Returns:
            Processed result.
        """
        pass
```

**Step 2: Implement Concrete Provider**

```python
# backend/app/services/[concrete_provider].py

import logging
from app.services.[service_name]_base import SomeDependency

logger = logging.getLogger(__name__)


class ConcreteProvider(SomeDependency):
    """Concrete implementation of SomeDependency.

    This is the actual implementation with real logic/API calls.
    """

    def __init__(self, api_key: str):
        """Initialize with API credentials.

        Args:
            api_key: API key for the service.
        """
        self.api_key = api_key

    async def do_something(self, data: str) -> str:
        """Implement abstract method with real logic.

        Args:
            data: Input data.

        Returns:
            Processed result.

        Raises:
            RuntimeError: If the API call fails.
        """
        try:
            logger.debug("Calling API with data: %s", data[:50])
            # Real implementation here (API calls, etc.)
            result = f"processed: {data}"
            logger.info("API call succeeded")
            return result
        except Exception as e:
            logger.error("API error: %s", e, exc_info=True)
            raise RuntimeError(f"API error: {e}") from e
```

**Step 3: Create Service That Uses the Dependency**

```python
# backend/app/services/[service_name].py

import logging
from app.services.[service_name]_base import SomeDependency

logger = logging.getLogger(__name__)


class MyService:
    """Service that uses an injected dependency.

    Takes dependency in __init__, doesn't create it.
    Works with ANY implementation of SomeDependency.
    """

    def __init__(self, dependency: SomeDependency):
        """Initialize with injected dependency.

        Args:
            dependency: Implementation of SomeDependency (e.g., ConcreteProvider).
        """
        self.dependency = dependency

    async def some_method(self, input_data: str) -> str:
        """Do something using the injected dependency.

        Args:
            input_data: Input to process.

        Returns:
            Processed result.
        """
        logger.info("Processing: %s", input_data[:50])
        result = await self.dependency.do_something(input_data)
        logger.info("Result: %s", result[:50])
        return result
```

**Step 4: Create Tests with Mock Dependency**

```python
# backend/tests/services/test_[service_name].py

import pytest
from unittest.mock import AsyncMock
from app.services.[service_name] import MyService
from app.services.[service_name]_base import SomeDependency


@pytest.fixture
def mock_dependency():
    """Mock implementation of SomeDependency (for testing).

    This allows us to test MyService without calling real APIs.
    """
    mock = AsyncMock(spec=SomeDependency)
    mock.do_something.return_value = "mocked result"
    return mock


@pytest.fixture
def service(mock_dependency):
    """Create service with mocked dependency."""
    return MyService(dependency=mock_dependency)


@pytest.mark.asyncio
async def test_some_method_success(service, mock_dependency):
    """Test happy path."""
    result = await service.some_method("input")

    assert result == "mocked result"
    mock_dependency.do_something.assert_called_once()


@pytest.mark.asyncio
async def test_some_method_dependency_failure(service, mock_dependency):
    """Test error handling when dependency fails."""
    mock_dependency.do_something.side_effect = Exception("Service down")

    with pytest.raises(Exception):
        await service.some_method("input")
```

### Real Example: LLM Service with OpenAI Provider

This shows the actual pattern used in V2:

**1. Abstract Base (llm_base.py):**

```python
# backend/app/services/llm_base.py
from typing import Protocol

class LLMProvider(Protocol):
    """Abstract LLM provider interface."""

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Generate a chat completion. Subclasses implement this.

        Args:
            response_format: Output format hint. "json" for structured JSON output,
                None (default) for plain text. V2.1 will add true structured outputs.
        """
        ...
```

**2. Concrete Implementation (openai_provider.py):**

```python
# backend/app/services/openai_provider.py
from openai import AsyncOpenAI
from app.services.llm_base import LLMProvider

class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLMProvider."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Implement with real OpenAI API call."""
        # Build request
        create_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # OpenAI supports JSON mode - pass if requested
        if response_format == "json":
            create_kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**create_kwargs)
        return (response.choices[0].message.content or "").strip()
```

**3. Service Uses It (llm.py):**

```python
# backend/app/services/llm.py
from app.services.llm_base import LLMProvider

class LLMService:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def chat_completion(self, system_prompt, user_prompt, **kwargs):
        return await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            **kwargs
        )
```

**4. In V3, Add Claude Support (anthropic_provider.py):**

```python
# backend/app/services/anthropic_provider.py
from anthropic import AsyncAnthropic
from app.services.llm_base import LLMProvider

class AnthropicProvider(LLMProvider):
    """Claude implementation of LLMProvider."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-opus-4-6"

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Implement with real Claude API call.

        Note: response_format is accepted but ignored. Anthropic's structured outputs
        (V2.1) will handle this parameter properly.
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return (response.content[0].text or "").strip()
```

**No changes needed to LLMService!** Just swap the provider in dependency injection.

### Key Distinction

| Component                   | Purpose                  | Example                                       |
| --------------------------- | ------------------------ | --------------------------------------------- |
| **Base (ABC)**              | Defines the interface    | `LLMProvider` (abstract)                      |
| **Concrete Implementation** | Implements the interface | `OpenAIProvider`, `AnthropicProvider`         |
| **Service**                 | Uses the dependency      | `LLMService` (doesn't know which provider)    |
| **Tests**                   | Mock the dependency      | `mock_provider = AsyncMock(spec=LLMProvider)` |

**The service doesn't know or care which provider it gets. That's the power of DI.**

---

## Part 2: Repository Pattern (For Data Access)

**IMPORTANT:** Repositories should raise domain exceptions (EntityNotFoundError, DatabaseError),
not HTTPException. This keeps repositories reusable across contexts (routes, services, background jobs).

See CLAUDE.md "Error Handling: Domain Exceptions Pattern" for full pattern.

### The Pattern

**Bad (Mixed concerns - data access in route):**

```python
# ❌ Don't do this - routes/chat.py

@router.post("/api/chat")
async def ask_meno(payload: ChatRequest, user_id: CurrentUser, client: SupabaseClient):
    # Data access mixed with business logic
    response = (
        await client.table("users")
        .select("journey_stage, date_of_birth")
        .eq("id", user_id)
        .execute()
    )
    if response.data:
        journey_stage = response.data[0].get("journey_stage")

    # ... more business logic
```

**Good (Repository handles data access):**

```python
# ✅ Do this - repositories/user_repository.py

from app.exceptions import EntityNotFoundError, DatabaseError

class UserRepository:
    def __init__(self, client: AsyncClient):
        self.client = client

    async def get_context(self, user_id: str) -> tuple[str, int | None]:
        """Get user journey stage and age.

        Raises:
            DatabaseError: Database operation failed.
        """
        try:
            response = (
                await self.client.table("users")
                .select("journey_stage, date_of_birth")
                .eq("id", user_id)
                .execute()
            )
            if response.data:
                row = response.data[0]
                journey_stage = row.get("journey_stage") or "unsure"
                dob_raw = row.get("date_of_birth")
                age = self._calculate_age(dob_raw) if dob_raw else None
                return journey_stage, age
            return "unsure", None
        except Exception as exc:
            logger.error("Failed to fetch user context: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to fetch user context: {exc}") from exc

    @staticmethod
    def _calculate_age(dob: str) -> int:
        """Calculate age from ISO date string."""
        from datetime import date
        dob_date = date.fromisoformat(dob)
        today = date.today()
        return (
            today.year
            - dob_date.year
            - ((today.month, today.day) < (dob_date.month, dob_date.day))
        )


# Then in routes/chat.py - domain exceptions caught by global handlers:

@router.post("/api/chat")
async def ask_meno(
    payload: ChatRequest,
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
):
    # Clean and focused
    journey_stage, age = await user_repo.get_context(user_id)
    # ... rest of business logic
```

### Repository Template for V2

Use this for EVERY repository (user, symptoms, conversation, appointment, period, medication):

```python
# backend/app/repositories/[entity]_repository.py

import logging
from typing import Optional
from supabase import AsyncClient
from app.exceptions import EntityNotFoundError, DatabaseError

logger = logging.getLogger(__name__)


class EntityRepository:
    """Data access for [Entity] entity.

    Handles all Supabase queries for [Entity].
    Keeps data access logic out of routes and services.
    Raises domain exceptions (not HTTPException) for clean separation of concerns.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def get(self, entity_id: str, user_id: str) -> Optional[dict]:
        """Fetch a single entity by ID (with user ownership check).

        Args:
            entity_id: ID of entity to fetch.
            user_id: Current user ID (for RLS verification).

        Returns:
            Entity dict or None if not found.

        Raises:
            EntityNotFoundError: Entity not found or doesn't belong to user.
            DatabaseError: Database operation failed.
        """
        try:
            response = (
                await self.client.table("[table_name]")
                .select("*")
                .eq("id", entity_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to fetch entity: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError(f"Entity {entity_id} not found")

        return response.data[0]

    async def create(self, user_id: str, data: dict) -> dict:
        """Create new entity.

        Args:
            user_id: Owner of entity.
            data: Entity data (don't include user_id, let insert add it).

        Returns:
            Created entity with ID.

        Raises:
            HTTPException: 400 for validation errors, 500 for DB errors.
        """
        try:
            response = (
                await self.client.table("[table_name]")
                .insert({"user_id": user_id, **data})
                .execute()
            )
        except Exception as exc:
            logger.error("DB insert failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to create entity",
            )

        if not response.data:
            logger.error("Supabase returned no data after insert")
            raise HTTPException(
                status_code=500,
                detail="Failed to create entity",
            )

        return response.data[0]

    async def update(self, entity_id: str, user_id: str, data: dict) -> dict:
        """Update entity (with ownership check).

        Args:
            entity_id: ID of entity to update.
            user_id: Current user ID (for RLS).
            data: Fields to update.

        Returns:
            Updated entity.

        Raises:
            HTTPException: 404 if not found, 500 for DB errors.
        """
        try:
            response = (
                await self.client.table("[table_name]")
                .update(data)
                .eq("id", entity_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB update failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to update entity",
            )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Entity not found",
            )

        return response.data[0]

    async def delete(self, entity_id: str, user_id: str) -> None:
        """Delete entity (with ownership check).

        Args:
            entity_id: ID of entity to delete.
            user_id: Current user ID (for RLS).

        Raises:
            HTTPException: 404 if not found, 500 for DB errors.
        """
        try:
            response = (
                await self.client.table("[table_name]")
                .delete()
                .eq("id", entity_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB delete failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to delete entity",
            )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Entity not found",
            )
```

### Repository Tests Template

```python
# backend/tests/repositories/test_[entity]_repository.py

import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    return AsyncMock()


@pytest.fixture
def repository(mock_supabase):
    """Create repository with mocked Supabase."""
    from app.repositories.[entity]_repository import EntityRepository
    return EntityRepository(client=mock_supabase)


@pytest.mark.asyncio
async def test_get_success(repository, mock_supabase):
    """Test fetching entity."""
    mock_supabase.table().select().eq().eq().execute.return_value = AsyncMock(
        data=[{"id": "123", "user_id": "user1", "name": "Test"}]
    )

    result = await repository.get("123", "user1")

    assert result["id"] == "123"
    assert result["name"] == "Test"


@pytest.mark.asyncio
async def test_get_not_found(repository, mock_supabase):
    """Test fetching non-existent entity."""
    mock_supabase.table().select().eq().eq().execute.return_value = AsyncMock(
        data=[]
    )

    with pytest.raises(HTTPException) as exc_info:
        await repository.get("999", "user1")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_success(repository, mock_supabase):
    """Test creating entity."""
    created_entity = {"id": "new-123", "user_id": "user1", "name": "New"}
    mock_supabase.table().insert().execute.return_value = AsyncMock(
        data=[created_entity]
    )

    result = await repository.create("user1", {"name": "New"})

    assert result["id"] == "new-123"


@pytest.mark.asyncio
async def test_create_db_error(repository, mock_supabase):
    """Test create handles DB errors."""
    mock_supabase.table().insert().execute.side_effect = Exception("DB down")

    with pytest.raises(HTTPException) as exc_info:
        await repository.create("user1", {"name": "New"})

    assert exc_info.value.status_code == 500
```

---

## Part 3: Route with DI (Thin & Focused)

### The Pattern

**Before Refactor (Too Much Logic):**

```python
# ❌ 100+ lines doing 8+ things

@router.post("/api/chat")
async def ask_meno(payload: ChatRequest, user_id: CurrentUser, client: SupabaseClient):
    # Validation
    if not payload.message.strip():
        raise HTTPException(...)

    # Data access (should be in repo)
    response = await client.table("users").select(...).execute()
    journey_stage = response.data[0].get("journey_stage") if response.data else "unsure"

    # More data access
    response = await client.table("symptom_summary_cache").select(...).execute()
    symptom_summary = response.data[0].get("summary_text") if response.data else ""

    # RAG (should be in service)
    chunks = await retrieve_relevant_chunks(payload.message, top_k=5)

    # Deduplication (should be in service)
    seen_urls = set()
    unique_chunks = []
    for chunk in chunks:
        if chunk.get("source_url") not in seen_urls:
            unique_chunks.append(chunk)
            seen_urls.add(chunk.get("source_url"))

    # Prompt building (should be in service)
    system_prompt = f"You are ...\n\nUser context:\n{journey_stage}\n\nSources:\n{unique_chunks}"

    # LLM call (should be in service)
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(...)

    # Citation handling (should be in service)
    cleaned_text = _sanitize_citations(response.choices[0].message.content)
    citations = _extract_citations(cleaned_text, unique_chunks)

    # Persistence (should be in repo)
    response = await client.table("conversations").update(...).execute()

    # Response assembly
    return ChatResponse(...)
```

**After Refactor (Thin & Focused):**

```python
# ✅ 30 lines doing orchestration only

from app.repositories.user_repository import UserRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services.llm import LLMService
from app.services.citations import CitationService
from app.rag.retrieval import RAGService


@router.post("/api/chat", response_model=ChatResponse)
async def ask_meno(
    payload: ChatRequest,
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
    symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RAGService = Depends(get_rag_service),
    citation_service: CitationService = Depends(get_citation_service),
) -> ChatResponse:
    """Ask Meno a question with RAG grounding and citations."""

    # Validate
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Gather context (services handle complexity)
    journey_stage, age = await user_repo.get_context(user_id)
    symptom_summary = await symptoms_repo.get_summary(user_id)
    existing_messages = await conversation_repo.load(payload.conversation_id, user_id)

    # Get knowledge (services handle retrieval + dedup)
    chunks = await rag_service.retrieve(message)

    # Generate response (services handle all complexity)
    response_text = await llm_service.chat_completion(
        system_prompt=llm_service.build_system_prompt(journey_stage, age, symptom_summary, chunks),
        user_prompt=message,
        max_tokens=800,
        temperature=0.5,
    )

    # Extract citations (service handles logic)
    response_text = citation_service.sanitize_and_renumber(response_text, len(chunks))
    citations = citation_service.extract(response_text, chunks)

    # Persist conversation
    messages = existing_messages + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": response_text, "citations": citations},
    ]
    conversation_id = await conversation_repo.save(payload.conversation_id, user_id, messages)

    return ChatResponse(message=response_text, citations=citations, conversation_id=conversation_id)
```

**Why This Is Better:**

- Route is 30 lines instead of 100+
- Each line is clear: what is it doing?
- Services handle complexity
- Repositories handle data access
- Easy to test (just mock the dependencies)
- Easy to change (modify service, not route)

### Dependency Injection in FastAPI

**In `backend/app/api/dependencies.py`:**

```python
from fastapi import Depends
from supabase import AsyncClient
from app.core.supabase import get_client
from app.repositories.user_repository import UserRepository
from app.services.llm import LLMService
from app.services.openai_provider import OpenAIProvider
from app.core.config import settings


def get_user_repo(client: AsyncClient = Depends(get_client)) -> UserRepository:
    """Dependency for UserRepository."""
    return UserRepository(client=client)


def get_llm_service() -> LLMService:
    """Dependency for LLMService."""
    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    return LLMService(provider=provider)


# Then in routes:
async def some_endpoint(
    user_repo: UserRepository = Depends(get_user_repo),
    llm_service: LLMService = Depends(get_llm_service),
):
    # Use them
    context = await user_repo.get_context(user_id)
    response = await llm_service.chat_completion(...)
```

---

## Part 4: Testing Patterns

### Pure Function Tests (No Mocks Needed)

```python
# backend/tests/services/test_stats.py

from app.services.stats import calculate_frequency_stats


def test_frequency_stats_counts_and_sorts():
    """Test that stats are counted and sorted descending."""
    logs = [
        {"symptoms": ["id-a", "id-b"]},
        {"symptoms": ["id-a"]},
    ]
    ref = {
        "id-a": {"name": "Fatigue", "category": "physical"},
        "id-b": {"name": "Sleep", "category": "sleep"},
    }

    result = calculate_frequency_stats(logs, ref)

    assert len(result) == 2
    assert result[0].symptom_id == "id-a"  # Count 2, first
    assert result[0].count == 2
    assert result[1].symptom_id == "id-b"  # Count 1, second
    assert result[1].count == 1
```

### Service Tests (Mock Dependencies)

```python
# backend/tests/services/test_llm.py

import pytest
from unittest.mock import AsyncMock
from app.services.llm import LLMService


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    mock = AsyncMock()
    mock.chat_completion.return_value = "Generated response"
    return mock


@pytest.fixture
def service(mock_provider):
    """Service with mocked provider."""
    return LLMService(provider=mock_provider)


@pytest.mark.asyncio
async def test_generate_summary_calls_provider(service, mock_provider):
    """Test that service calls provider correctly."""
    result = await service.generate_symptom_summary([], [], ("2026-01-01", "2026-02-01"))

    assert result == "Generated response"
    mock_provider.chat_completion.assert_called_once()

    # Verify it was called with right args
    call_args = mock_provider.chat_completion.call_args
    assert "system_prompt" in call_args.kwargs
    assert "user_prompt" in call_args.kwargs
```

### Route Tests (Mock Everything)

```python
# backend/tests/api/routes/test_appointment.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_context_endpoint_creates_appointment(auth_header):
    """Test appointment context endpoint."""
    response = client.post(
        "/api/appointment-prep/context",
        json={
            "appointment_type": "new_provider",
            "goal": "understand_where_i_am",
            "dismissed_before": "multiple",
        },
        headers=auth_header,
    )

    assert response.status_code == 201
    data = response.json()
    assert "appointment_id" in data
    assert data["next_step"] == "narrative"


@pytest.mark.asyncio
async def test_narrative_endpoint_calls_llm(auth_header, mock_llm_service):
    """Test that narrative endpoint calls LLM."""
    with patch("app.api.routes.appointment.get_llm_service", return_value=mock_llm_service):
        response = client.post(
            "/api/appointment-prep/narrative",
            json={"appointment_id": "apt-123"},
            headers=auth_header,
        )

    assert response.status_code == 200
    mock_llm_service.chat_completion.assert_called_once()
```

---

## Part 5: Claude Code Prompt Examples

### Prompt for Service Creation

```markdown
I'm implementing a new service for V2: [ServiceName].

Follow the patterns in CLAUDE.md "Service Layer" section and reference Context7 MCP for FastAPI/async patterns.

Requirements:

- Use dependency injection (take dependencies in **init**, not hardcoded)
- Pure functions where possible (no side effects)
- Complete type hints
- Docstrings for all public methods (explain why, not just what)
- No database access (that's the repository's job)
- Comprehensive error handling
- Logging of important operations

Use this structure:

1. Define dependency interface (Protocol)
2. Create service class with injected dependency
3. Implement methods
4. Create tests with mocked dependency

Reference:

- CLAUDE.md: "Code Standards" → "Python (Backend)" section for style
- DESIGN.md: Section on [relevant feature] for data model
- This code example file: "Part 1: Dependency Injection Pattern"

Start with the dependency interface, then the service class.
```

### Prompt for Repository Creation

```markdown
I'm creating a [Entity]Repository for V2.

Follow the patterns in the "Part 2: Repository Pattern" section of the code examples.

This repository handles all data access for [Entity]. It should:

- Take AsyncClient in **init**
- Have get(), create(), update(), delete() methods
- Use Supabase queries for [table_name]
- Enforce user ownership (all queries filter by user_id)
- Return typed Pydantic models where possible
- Handle errors with proper HTTPExceptions
- Log important operations
- Be fully testable (all Supabase calls are mockable)

Data model (from DESIGN.md):
[Paste relevant schema info]

Reference:

- This code examples file: "Part 2: Repository Pattern"
- CLAUDE.md: "Code Standards" for error handling patterns
- Context7 MCP: For Supabase SDK patterns

Start with the class definition and **init**, then implement each CRUD method.
```

### Prompt for Route Creation

```markdown
I'm creating endpoints for [feature] in V2.

Follow the "Part 3: Route with DI (Thin & Focused)" pattern.

Requirements:

- Each route should be 20-40 lines maximum
- All complexity goes to services/repositories
- Dependencies injected via FastAPI's Depends()
- Proper status codes (201 for create, 204 for delete, etc.)
- Auth enforcement (CurrentUser dependency)
- Input validation (Pydantic models)
- Proper error responses (400, 404, 500)
- Docstrings explaining what the endpoint does
- Logging of important operations

Routes needed:

- [list endpoints here with methods and purposes]

Reference:

- This code examples file: "Part 3: Route with DI"
- CLAUDE.md: "API design" section
- DESIGN.md: Section on [feature] for expected endpoints
- Context7 MCP: For FastAPI patterns

Inject these dependencies:

- [repository] = Depends(get\_[repository])
- [service] = Depends(get\_[service])

Use the async ask_meno example as a template for structure.
```

### Prompt for Test Creation

```markdown
I'm writing comprehensive tests for [feature].

Follow the patterns in "Part 4: Testing Patterns" from the code examples.

Test coverage needed:

1. Happy path (everything works)
2. Auth enforcement (401 without token)
3. Input validation (400 for bad input)
4. Not found (404 for missing entity)
5. Server errors (500 for DB failures)
6. Edge cases: [list specific edge cases]

Reference:

- This code examples file: "Part 4: Testing Patterns"
- CLAUDE.md: "Testing Strategy" section
- Existing tests in backend/tests/ for patterns

Use these fixtures:

- mock_supabase: AsyncMock for database
- auth_header: Valid auth token
- [service]\_mock: Mocked service

Test naming: test*[endpoint]*[scenario]\_[expected_result]

Aim for 80%+ coverage on new code.
```

---

## Part 6: Quality Checklist for Every PR/Commit

Before committing code, verify:

### Code Quality

- [ ] Type hints on all function signatures
- [ ] Docstrings on all public functions/classes
- [ ] No hardcoded dependencies (use DI)
- [ ] No database access in services (only repositories)
- [ ] Error handling with proper status codes
- [ ] Logging of important operations
- [ ] No code duplication (DRY)

### Testing

- [ ] All tests pass (`pytest --cov=app`)
- [ ] 80%+ coverage on new code
- [ ] Happy path + error cases + edge cases tested
- [ ] Mocking used correctly (no real API calls)

### Standards Compliance

- [ ] Follows patterns from CLAUDE.md
- [ ] Follows patterns from this code examples file
- [ ] Uses FastAPI best practices (Context7 MCP if unsure)
- [ ] Uses async/await correctly (no blocking calls)
- [ ] Uses Supabase SDK correctly

### Documentation

- [ ] Docstrings are clear and explain why, not just what
- [ ] Comments for non-obvious logic
- [ ] README/DESIGN.md updated if adding new feature

### Security

- [ ] All endpoints require auth
- [ ] RLS policies enforced (user can only see own data)
- [ ] No secrets in code
- [ ] No PII in logs (hash user IDs)

---

## Part 7: Retry & Resilience Patterns

### Why Retry?

External services (OpenAI, Claude, Supabase, etc.) can fail transiently:
- **Rate limits (429)** — common when processing lots of LLM calls
- **Timeouts** — network latency, service load
- **Connection errors** — temporary network issues

For critical user flows (appointment prep, export generation), a single transient failure causes hard errors. Retry logic makes the app resilient.

### Pattern: @retry_transient Decorator

All external API calls should have retry logic. Use the `@retry_transient` decorator from `app/utils/retry.py`.

**Example: LLM Provider with Retry**

```python
# backend/app/services/openai_provider.py

import logging
from openai import AsyncOpenAI
from app.utils.retry import retry_transient

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI implementation with automatic retry on transient failures."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"

    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Call OpenAI API.

        Automatically retries on:
        - Timeouts (network latency)
        - Rate limits (429)
        - Connection errors

        Does NOT retry on:
        - Auth errors (401) — permanent
        - Not found (404) — permanent
        - Bad request (400) — permanent

        See app/utils/retry.py for retry logic.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()
```

### How Retry Works

1. **First call:** Attempt API call normally
2. **Transient error:** Catch it (timeout, connection error, 429), wait 1 second, retry
3. **Still failing:** Wait 2 seconds (exponential backoff), retry again
4. **Still failing:** Wait 4 seconds (capped at max_wait=10), retry once more
5. **All retries exhausted:** Re-raise exception to caller (route catches it)

### Retry Behavior Summary

| Scenario | Behavior |
|----------|----------|
| Success on 1st attempt | Return immediately |
| Timeout on 1st, success on 2nd | Wait 1s, retry, return |
| Timeout on 1st & 2nd, success on 3rd | Wait 1s, retry, wait 2s, retry, return |
| Timeout on all 3 attempts | Wait 1s, 2s, 4s, then raise error to caller |
| 401 Unauthorized | Don't retry, raise immediately |
| 404 Not Found | Don't retry, raise immediately |
| Rate limit (429) | Retry with exponential backoff (up to 10s waits) |

### Customizing Retry Behavior

```python
# More aggressive: 5 attempts, up to 30 second waits
@retry_transient(max_attempts=5, initial_wait=1, max_wait=30)
async def call_slow_api():
    pass

# Conservative: 2 attempts, quick waits
@retry_transient(max_attempts=2, initial_wait=0.5, max_wait=5)
async def call_fast_api():
    pass
```

### When to Add @retry_transient

**YES, add retry:**
- External API calls (OpenAI, Claude, Anthropic, Supabase storage, etc.)
- Any network-dependent operation
- LLM provider methods
- Storage/file upload operations

**NO, don't add retry:**
- Database queries (connection is separate from query)
- Local function calls
- Validation logic
- Auth checks (401 is permanent)

### Testing Retry Logic

When testing decorated functions, the retry logic is transparent — the mock will be called multiple times:

```python
@pytest.mark.asyncio
async def test_retries_on_timeout():
    """Test that timeout is retried."""
    provider = OpenAIProvider("fake-key")

    call_count = 0
    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("timeout")
        return Mock(choices=[Mock(message=Mock(content="Success"))])

    provider.client.chat.completions.create = mock_create
    result = await provider.chat_completion("system", "user")

    assert result == "Success"
    assert call_count == 2  # Called twice (retry worked)
```

### Implementation Details

See `backend/app/utils/retry.py`:
- `retry_transient()` — Decorator that applies retry logic
- `is_retryable_exception()` — Determines if exception is transient
- Automatically logs each retry attempt as warning
- Uses tenacity library for robust, tested retry logic

---

## Quick Reference: File Templates

### New Service Template

```
backend/app/services/[service_name].py
└── Copy from "Part 1: Dependency Injection" example
└── Create test file: backend/tests/services/test_[service_name].py
```

### New Repository Template

```
backend/app/repositories/[entity]_repository.py
└── Copy from "Part 2: Repository Pattern" example
└── Create test file: backend/tests/repositories/test_[entity]_repository.py
```

### New Route Template

```
backend/app/api/routes/[feature].py
└── Copy from "Part 3: Route with DI" example
└── Create test file: backend/tests/api/routes/test_[feature].py
```

---

## When in Doubt

1. **Reference CLAUDE.md** — "Code Standards" section has definitive patterns
2. **Reference DESIGN.md** — Architecture and data model details
3. **Use Context7 MCP** — For latest FastAPI, Pydantic, Supabase patterns
4. **Copy existing code** — Find similar patterns in current codebase
5. **Check the examples** — Use this file as reference

---

## Summary

**DI ensures:**

- ✅ Testable code (inject mocks)
- ✅ Flexible code (swap implementations)
- ✅ Clear code (dependencies explicit)

**Repository pattern ensures:**

- ✅ Data access isolated
- ✅ Easy to swap databases
- ✅ Services stay focused

**Thin routes ensure:**

- ✅ Easy to understand
- ✅ Easy to test
- ✅ Easy to modify

**This code quality level = faster V2 development + confident refactoring.**
