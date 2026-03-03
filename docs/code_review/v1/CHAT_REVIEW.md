# Chat Route Code Quality Analysis

**Date:** March 2, 2026
**Status:** Learning-Focused Review (No refactoring yet)
**Reviewer Notes:** Extensive logging, good error handling, but single responsibility violations in main endpoint

---

## Executive Summary

The chat route is **well-structured but overloaded**. The main endpoint (`ask_meno()`) orchestrates too many concerns:

- Context assembly (user data, symptoms)
- Conversation persistence (load/save)
- RAG orchestration (retrieval, deduplication)
- Prompt building
- LLM integration
- Citation handling

**Main Issue:** Testing the endpoint requires mocking ~10+ dependencies. Moving logic to services would make:

1. Each piece testable in isolation
2. The route thin and readable
3. Logic reusable (e.g., citation handling in other endpoints)
4. Swappable data layer (not locked into Supabase)

---

## Detailed Findings

### Strengths ✅

**Code Organization:**

- Functions grouped logically (Supabase helpers, OpenAI call, endpoint)
- Private helpers prefixed with `_`
- Clear section headers separate concerns visually

**Error Handling:**

- Proper HTTPException with status codes (400, 404, 500)
- Graceful degradation (empty RAG chunks → answer without sources)
- Try/catch blocks with informative error logging

**Async/Await:**

- All I/O operations properly awaited (no blocking calls)
- Parallel context gathering (user context + symptom summary awaited together)
- No synchronous database calls mixed in

**Logging:**

- Every important operation logged with context (user_id, operation name, data)
- DEBUG logs for detailed tracing
- WARNING/ERROR logs for issues
- Token usage tracked for cost monitoring

**Docstrings:**

- Functions have clear docstrings explaining purpose, args, raises
- Error scenarios documented

**Citation Logic:**

- Robust phantom citation removal (handles multiple formats)
- Smart renumbering to match extraction order
- Good regex patterns with word boundary handling

**Deduplication:**

- Smart deduplication by (base_url, section_name), not just URL
- Handles fragment stripping correctly
- Logs deduplication results

---

### Problems 🔴

### 1. Main Endpoint Does Too Much (100+ lines)

**Current `ask_meno()` responsibilities:**

1. Request validation (message not empty)
2. Context assembly (user journey stage, age)
3. Symptom summary retrieval
4. Conversation loading (existing messages)
5. RAG orchestration (retrieval + deduplication)
6. Prompt building coordination
7. OpenAI API call
8. Citation sanitization + extraction
9. Message history building
10. Conversation persistence
11. Response assembly

**Impact:**

- Hard to test (mock 10+ dependencies)
- Hard to understand flow (too many steps)
- Hard to reuse logic (buried in endpoint)
- Hard to change (touching one thing affects many)

**Example: Testing ask_meno()**
Current mocking requirements:

```python
# This is what you'd have to mock:
mock_supabase.table('users').select().eq().execute()  # user context
mock_supabase.table('symptom_summary_cache').select().eq().order().limit().execute()  # symptoms
mock_supabase.table('conversations').select().eq().execute()  # load conversation
retrieve_relevant_chunks()  # RAG
AsyncOpenAI()  # LLM
mock_supabase.table('conversations').update().eq().execute()  # save conversation

# That's 6+ complex mocks for ONE endpoint
```

After refactoring, testing ask_meno() would be:

```python
# Mock only the services it calls:
mock_context_service.get_context() → returns tuple
mock_rag_service.retrieve() → returns chunks
mock_llm_service.chat() → returns text
mock_conversation_service.load() → returns messages
mock_conversation_service.save() → returns ID

# 5 simple mocks instead of 6+ complex ones
```

### 2. Data Access Tightly Coupled to Route

**Current pattern:**

- Supabase AsyncClient passed directly to route
- Queries scattered across helper functions
- No abstraction layer
- Hard to change database without rewriting helpers

**Problems:**

- If you switched from Supabase to PostgreSQL directly, you'd rewrite `_fetch_user_context()`, `_fetch_symptom_summary()`, `_load_conversation()`, `_save_conversation()`
- If you added caching, you'd have to update each helper
- If you needed to add audit logging, you'd have to update each helper
- Queries are mixed with business logic

**Better approach: Data Access Layer/Repository**

```python
# Instead of:
async def _fetch_user_context(user_id, client):
    response = await client.table('users').select(...).eq(...).execute()
    # parse response
    return journey_stage, age

# Have:
class UserRepository:
    async def get_context(self, user_id: str) -> tuple[str, int | None]:
        # Implementation details hidden
        return journey_stage, age

# Now if you switch databases:
# Only UserRepository changes
# ask_meno() doesn't care
```

### 3. Citation Logic is Complex (80+ lines)

**Current split:**

- `_sanitize_and_renumber_citations()` — 60+ lines of regex + state management
- `_extract_citations()` — 30+ lines of regex + mapping

**Problems:**

- Tightly coupled to response text format
- Hard to test with complex regex patterns
- Could be reused by other endpoints (future chat variants, debugging, etc.)

**Better approach: CitationService**

```python
class CitationService:
    def sanitize_and_renumber(self, text: str, max_sources: int) -> tuple[str, list[int]]:
        # All the complex logic here
        return cleaned_text, removed_indices

    def extract(self, text: str, chunks: list[dict]) -> list[Citation]:
        # All the extraction logic here
        return citations
```

Why? Because citation handling is a distinct domain:

- It has its own complexity
- It's tested separately
- It could be used by other features (debugging UI, citation analytics, etc.)

### 4. Helper Functions Are Good But Could Be Part of Services

**Current helpers that could move:**

| Function                             | Purpose             | Better As                                 |
| ------------------------------------ | ------------------- | ----------------------------------------- |
| `_fetch_user_context()`              | User data access    | `UserRepository.get_context()`            |
| `_fetch_symptom_summary()`           | Symptom data access | `SymptomsRepository.get_summary()`        |
| `_load_conversation()`               | Load conversation   | `ConversationRepository.load()`           |
| `_save_conversation()`               | Save conversation   | `ConversationRepository.save()`           |
| `_call_openai()`                     | LLM integration     | `LLMService.chat_completion()`            |
| `_build_system_prompt()`             | Prompt assembly     | `PromptService.build_system_prompt()`     |
| `_sanitize_and_renumber_citations()` | Citation handling   | `CitationService.sanitize_and_renumber()` |
| `_extract_citations()`               | Citation handling   | `CitationService.extract()`               |

**Good news:** These are already decoupled from the endpoint. They're testable.
**The issue:** They're still helpers in the same file, not organized as services.

---

## Refactoring Roadmap

### If you were to refactor (not doing now, just mapping):

**Layer 1: Data Access (Repositories)**
Create `backend/app/repositories/` with:

- `UserRepository` — user context, journey stage, age calculation
- `SymptomsRepository` — symptom summary, caching
- `ConversationRepository` — load/save conversations

**Benefits:**

- Decouple from Supabase specifics
- Could swap to different database
- Could add caching transparently
- Could add audit logging centrally

**Files to create:**

- `backend/app/repositories/__init__.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/repositories/symptoms_repository.py`
- `backend/app/repositories/conversation_repository.py`

**Example:**

```python
# Before:
async def _fetch_user_context(user_id, client):
    response = await client.table('users').select(...).execute()
    if response.data:
        row = response.data[0]
        journey_stage = row.get('journey_stage') or 'unsure'
        ...
    return journey_stage, age

# After:
class UserRepository:
    def __init__(self, client: AsyncClient):
        self.client = client

    async def get_context(self, user_id: str) -> tuple[str, int | None]:
        # Same logic, but in a repository class
        ...
```

**Layer 2: Service Extraction**
Expand `backend/app/services/` with:

- `CitationService` — all citation handling
- `PromptService` — prompt building (currently in route)
- Possibly `AskMenoService` — orchestrate the flow

**Benefits:**

- Citation logic reusable by other endpoints
- Prompt building reusable
- ask_meno() becomes thin orchestrator

**Layer 3: Thin Route**
Refactored `ask_meno()` would be:

```python
async def ask_meno(payload: ChatRequest, user_id: CurrentUser, client: SupabaseClient):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Call services (they handle their own complexity)
    context = await user_repo.get_context(user_id)
    symptom_summary = await symptoms_repo.get_summary(user_id)
    conversation = await conversation_repo.load(payload.conversation_id, user_id)
    chunks = await rag_service.retrieve(message)

    # Orchestrate
    prompt = prompt_service.build(context, symptom_summary, chunks)
    response_text = await llm_service.chat(prompt, message)
    clean_text = citation_service.sanitize(response_text, len(chunks))
    citations = citation_service.extract(clean_text, chunks)

    # Persist
    messages = build_messages(conversation, message, response_text, citations)
    conversation_id = await conversation_repo.save(payload.conversation_id, user_id, messages)

    return ChatResponse(message=clean_text, citations=citations, conversation_id=conversation_id)
```

That's ~30 lines, super readable, testable.

---

## Testing Implications

### Current Testing Challenge

```python
# To test ask_meno(), you'd need to mock:
@pytest.fixture
async def test_ask_meno(mock_supabase, mock_openai, mock_rag):
    # 10+ mocks
    response = await ask_meno(
        ChatRequest(...),
        user_id="test-user",
        client=mock_supabase  # Complex mock
    )
    # Hard to test specific scenarios
```

### After Refactoring

```python
# Test ask_meno() with service mocks:
async def test_ask_meno(mock_user_repo, mock_rag_service, mock_llm_service, ...):
    # 5 simple mocks
    response = await ask_meno(ChatRequest(...), user_id="test-user", client=real_client)
    # Could even use real client if you want
    # Services are tested separately

# Test CitationService independently:
def test_citation_sanitization():
    service = CitationService()
    text = "This is good [Source 1] and phantom [Source 5]"
    clean = service.sanitize(text, max_sources=3)
    assert "[Source 5]" not in clean
    assert "[Source 1]" in clean
    # No mocks needed!

# Test UserRepository independently:
async def test_get_user_context(mock_supabase):
    repo = UserRepository(mock_supabase)
    context = await repo.get_context("test-user")
    assert context.journey_stage == "perimenopause"
    # Only mock Supabase, not the whole endpoint
```

---

## Decision: Refactor or Not?

**For V1:** No refactoring needed. The code works. The endpoint is long but functional.

**For V2:** Strongly recommend this refactoring pattern BEFORE you build new features:

1. Build UserRepository + SymptomsRepository + ConversationRepository from day 1
2. Extract CitationService from chat route logic
3. Build ask_meno() on top of these services
4. When you build appointment prep flow (V2 feature), it'll reuse UserRepository, CitationService, PromptService
5. Testing will be much easier

**Cost of NOT refactoring in V2:**

- Each new endpoint copies Supabase queries (code duplication)
- Testing becomes harder (more mocks needed)
- If you ever want to change databases, it's a huge refactor

**Cost of refactoring now:**

- ~4-6 hours of focused work
- Safer, faster V2 development

---

## Technical Debt Summary

| Item                         | Impact | Effort | Priority | Notes                                  |
| ---------------------------- | ------ | ------ | -------- | -------------------------------------- |
| Main endpoint too large      | High   | Medium | Medium   | Refactor before V2                     |
| No data access layer         | High   | Medium | Medium   | Will bite you in V2                    |
| Citation logic not reusable  | Medium | Low    | Low      | OK for now, extract in V2              |
| Supabase tightly coupled     | Medium | Medium | Medium   | Won't matter if staying with Supabase  |
| Prompt building not reusable | Medium | Low    | Low      | Extract when building appointment prep |

---
