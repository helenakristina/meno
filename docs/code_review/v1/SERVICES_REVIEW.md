# Service Layer Quality Analysis

**Date:** March 2, 2026
**Status:** Learning-focused review complete

---

## Executive Summary

**Overall Quality: 7/10 — Good Foundation, Some Inconsistencies**

✅ **Strengths:**

- Most services are **pure functions** (no side effects, testable)
- **Clear separation of concerns** (LLM, stats, providers, symptoms)
- **Excellent docstrings** and logging throughout
- **Type hints** are consistent and complete
- **Defensive programming** (null checks, error handling)

🟡 **Issues:**

- **Inconsistent patterns** across services (sync vs async, dependency injection)
- **LLM client is hardcoded** (not injected, makes testing harder)
- **Symptom service mixes concerns** (validation + DB access)
- **Async not justified** in some functions
- **No data access abstraction** (DB queries scattered in routes + services)

---

## Service-by-Service Analysis

### 1. `llm.py` (225 lines) — LLM Integration

**Purpose:** Generate summaries, provider questions, and calling scripts via OpenAI

**Functions:**

- `_client()` — Create AsyncOpenAI client
- `generate_symptom_summary()` — 2–3 paragraph clinical summary
- `generate_provider_questions()` — 5–7 prep questions for provider visit
- `generate_calling_script()` — Script for calling provider office

#### Quality Assessment

**✅ Strengths:**

1. **Clear prompt engineering** — System prompts are explicit, well-structured, enforce guardrails
   - "logs show" language enforced (no diagnosis)
   - "never recommend treatment" rules clear
   - Temperature and max_tokens tuned appropriately

2. **Good error handling** — Graceful degradation
   - Strips whitespace from responses
   - Handles empty responses
   - Logs token usage for cost tracking

3. **Well-documented** — Docstrings explain intent and guardrails
   - `generate_symptom_summary()`: Clear about "logs show" framing
   - `generate_provider_questions()`: Explicit about not requesting diagnoses

4. **Logging is thorough** — Every LLM call logged with context
   - Input summary (range, item counts)
   - Output size (for debugging)
   - Makes debugging easy

5. **Data preparation** — Transforms structured data (SymptomFrequency objects) into readable text
   - Picks top 10 symptoms, top 5 pairs (reasonable limits)
   - Formats for readability

#### 🔴 Issues:

1. **Client creation is hardcoded**

   ```python
   def _client() -> AsyncOpenAI:
       return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
   ```

   **Problem:** Can't inject mock client for testing. Every call to `_client()` creates a new instance.

   **Better approach:**

   ```python
   class LLMService:
       def __init__(self, client: AsyncOpenAI):
           self.client = client

       async def generate_symptom_summary(self, ...):
           response = await self.client.chat.completions.create(...)

   # In route:
   llm_service = LLMService(AsyncOpenAI(api_key=settings.OPENAI_API_KEY))
   # Or in tests:
   llm_service = LLMService(mock_client)
   ```

2. **Three functions doing similar work**
   - Each calls `_client().chat.completions.create()`
   - Each has identical try/error handling
   - Could be **extracted to a common `_call_llm()` helper**

   **Duplication:**

   ```python
   # All three functions do this:
   response = await _client().chat.completions.create(
       model=_MODEL,
       messages=[...],
       max_tokens=XXX,
       temperature=X.X,
   )
   text = (response.choices[0].message.content or "").strip()
   ```

3. **Async but no parallelization**
   - Functions are `async` but don't call anything else concurrently
   - Could be synchronous (only async because OpenAI client is async)
   - If you ever switched to a sync LLM library, you'd rewrite these

4. **No input validation**
   - `frequency_stats` could be empty (handled gracefully but not validated)
   - `generate_calling_script()` takes raw strings with no validation
   - Could use Pydantic models to enforce structure

#### Testing Challenge

**Current way (hard):**

```python
# Can't mock because _client() is hardcoded
async def test_generate_symptom_summary(mock_openai):
    # Can't inject mock_openai, _client() ignores it
    result = await generate_symptom_summary([...])
    # Impossible to test without hitting real OpenAI
```

**Better way (after refactoring):**

```python
async def test_generate_symptom_summary(mock_client):
    service = LLMService(mock_client)
    mock_client.chat.completions.create.return_value = ...
    result = await service.generate_symptom_summary([...])
    # Easy to test
```

#### Grade: 6/10

Good prompts, good logging, but testability issues and some code duplication.

---

### 2. `stats.py` (137 lines) — Statistical Calculations

**Purpose:** Pure calculations on symptom logs (no DB access, no side effects)

**Functions:**

- `calculate_frequency_stats()` — Count symptom occurrences
- `calculate_cooccurrence_stats()` — Find symptom pairs that occur together

#### Quality Assessment

**✅ Strengths:**

1. **Pure functions** — No side effects, no DB access, no external calls
   - Input: list of dicts, symptom reference dict
   - Output: typed models
   - Same input always gives same output ✅

2. **Excellent docstrings** — Document behavior and edge cases
   - Explain co-occurrence rate calculation
   - Note deduplication strategy (preserve order)
   - Explain min_threshold parameter

3. **Defensive programming**

   ```python
   if ref:
       stats.append(...)
   else:
       logger.warning("Symptom ID %s not found...", symptom_id)
   ```

   Logs data integrity issues instead of crashing

4. **Smart algorithms**
   - Uses `Counter` for efficient counting ✓
   - Uses `itertools.combinations()` for pairs (no duplicates) ✓
   - Deduplicates while preserving order: `list(dict.fromkeys(...))` ✓

5. **Constants for maintainability**

   ```python
   MAX_COOCCURRENCE_PAIRS = 10  # Clearly explained in comment
   ```

6. **Type hints are complete**
   ```python
   def calculate_frequency_stats(
       logs: list[dict],
       symptoms_reference: dict[str, dict],
   ) -> list[SymptomFrequency]:
   ```

#### 🟡 Issues (Minor):

1. **No input validation**

   ```python
   def calculate_frequency_stats(logs: list[dict], ...):
       # What if logs is None? Empty? Malformed?
       # Should validate before processing
   ```

2. **Error handling is one-way**
   - Logs warnings for missing symptom IDs
   - But doesn't tell caller how many were dropped
   - Could return a result object: `{stats: [...], warnings: [...]}`

3. **min_threshold parameter not well-used**
   ```python
   if co_count < min_threshold:
       continue  # Silently drops pairs
   ```
   Could log what was filtered out

#### Testing: Excellent

```python
def test_calculate_frequency_stats():
    logs = [
        {"symptoms": ["id-a", "id-b"]},
        {"symptoms": ["id-a"]},
    ]
    ref = {
        "id-a": {"name": "Fatigue", "category": "physical"},
        "id-b": {"name": "Sleep", "category": "sleep"},
    }
    result = calculate_frequency_stats(logs, ref)
    assert result[0].symptom_id == "id-a"
    assert result[0].count == 2
    # No mocks needed! Pure function.
```

#### Grade: 9/10

Excellent pure functions, great docstrings, solid algorithms. Minor edge case handling could be improved.

---

### 3. `providers.py` (186 lines) — Provider Search Logic

**Purpose:** Transform, filter, paginate, and aggregate provider data

**Functions:**

- `to_provider_card()` — Transform DB row to ProviderCard model
- `filter_and_paginate()` — Filter by city/insurance, sort, paginate
- `aggregate_states()` — Count providers per state
- `collect_insurance_options()` — Flatten and deduplicate insurance options
- `assemble_calling_script_prompts()` — Build system + user prompts for LLM

#### Quality Assessment

**✅ Strengths:**

1. **All pure functions** — No DB access, no side effects
   - Could be called from anywhere
   - Easily testable
   - Composable

2. **Smart filtering logic**
   - Two-phase city matching: exact match → substring fallback
   - Handles case-insensitivity gracefully
   - Insurance substring matching is flexible

3. **Good sorting strategy**

   ```python
   sorted(
       providers,
       key=lambda p: (
           0 if p.get("nams_certified") else 1,  # NAMS first
           (p.get("name") or "").lower()  # Then alphabetical
       ),
   )
   ```

   Multi-key sort is Pythonic and clear

4. **Pagination is correct**

   ```python
   offset = (page - 1) * page_size
   page_items = providers[offset : offset + page_size]
   total_pages = math.ceil(total / page_size) if total > 0 else 1
   ```

   Handles edge cases (no results, page beyond end)

5. **Insurance normalization is integrated**

   ```python
   insurance_accepted=normalize_insurance_list(row.get("insurance_accepted") or [])
   ```

   Converts raw DB data to clean display values

6. **Calling script prompt assembly is sophisticated**
   - Insurance blocks vary by type (Private, Medicaid, Medicare, Self-pay)
   - Conditional text based on whether patient knows plan name
   - Telehealth preference supported
   - Clear explanatory comments

#### 🟡 Issues:

1. **Insurance normalization is opaque**

   ```python
   from app.core.insurance_normalizer import normalize_insurance_list
   ```

   What does this do? Need to check another file. Could be clearer.

2. **Magic numbers in filter_and_paginate**

   ```python
   page_size: int  # What's valid? 10, 50, 100?
   ```

   Should have validation or constants

3. **Insurance enum coupling**

   ```python
   elif request.insurance_type == InsuranceType.private:
   ```

   If InsuranceType changes, breaks. Could use a dict for mapping:

   ```python
   INSURANCE_BLOCKS = {
       InsuranceType.private: "...",
       InsuranceType.medicaid: "...",
   }
   ```

4. **No validation of inputs**
   - `page` could be 0 or negative
   - `page_size` could be huge
   - `city` could be empty string
   - Should validate before processing

#### Testing: Good

```python
def test_filter_and_paginate():
    providers = [
        {"id": "1", "name": "Alice", "city": "NYC", ...},
        {"id": "2", "name": "Bob", "city": "LA", ...},
    ]
    result = filter_and_paginate(
        providers,
        city="NYC",
        insurance="Aetna",
        page=1,
        page_size=10,
    )
    assert result.total == 1
    assert result.providers[0].name == "Alice"
```

#### Grade: 8/10

Pure, well-structured functions. Minor validation and magic number issues.

---

### 4. `symptoms.py` (44 lines) — Symptom Validation

**Purpose:** Validate symptom IDs against the symptoms_reference table

**Function:**

- `validate_symptom_ids()` — Check that IDs exist in DB

#### Quality Assessment

**✅ Strengths:**

1. **Clear, focused purpose** — One thing, does it well
2. **Smart deduplication** — Removes duplicate IDs before querying DB
3. **Good error messages** — Lists invalid IDs in the exception detail
4. **Logging on error** — Logs failures for debugging

#### 🔴 Critical Issues:

1. **Mixes data access with validation** — This is a repository operation, not a service

   ```python
   async def validate_symptom_ids(symptom_ids: list[str], client: AsyncClient):
       # Should be in a repository, not a service
       result = await client.table("symptoms_reference").select("id").in_("id", unique_ids).execute()
   ```

   **Problem:** Couples this function to Supabase. Hard to swap DBs.

2. **Requires AsyncClient parameter** — Breaks dependency injection

   ```python
   # Caller has to pass client:
   await validate_symptom_ids(symptom_ids, client)

   # Better: inject into a service:
   service = SymptomService(client)
   await service.validate_ids(symptom_ids)
   ```

3. **Async but no reason** — This is just a query, could be sync or async
   - Reason for async: Supabase client is async
   - But that's an implementation detail
   - Could abstract away

4. **Should be in a repository** — This is pure data access
   ```python
   # Should be:
   class SymptomsRepository:
       async def validate_ids(self, ids: list[str]) -> None:
           ...
   ```

#### Testing: Tricky

```python
# Hard to test without mocking Supabase
async def test_validate_symptom_ids(mock_client):
    # Have to mock the entire client
    mock_client.table().select().in_().execute.return_value = ...
    await validate_symptom_ids(["valid-id"], mock_client)
```

#### Grade: 4/10

Good logic, but shouldn't be in services layer. This is a repository function.

---

## Service Pattern Analysis

### What Patterns Are Used?

| Service        | Pattern                         | Style      |
| -------------- | ------------------------------- | ---------- |
| `llm.py`       | Functions with hardcoded client | Imperative |
| `stats.py`     | Pure functions                  | Functional |
| `providers.py` | Pure functions                  | Functional |
| `symptoms.py`  | Function + DB access            | Mixed      |

### Observations:

1. **No service classes** — All functions, no classes (except LLM internally)
   - Pro: Simple, functional
   - Con: Can't inject dependencies easily

2. **No dependency injection pattern** — Dependencies are either:
   - Hardcoded (`_client()` in LLM)
   - Passed as parameter (`client` in symptoms)
   - Built into function (`stats.py` pure functions)

3. **Inconsistent async usage**
   - LLM: Async (justifiable—OpenAI client)
   - Stats: Sync (pure functions, no I/O)
   - Providers: Sync (pure functions)
   - Symptoms: Async (DB access)

4. **No repository layer** — Data access scattered:
   - `symptoms.py` has DB query
   - Chat route has `_fetch_user_context()`, `_fetch_symptom_summary()`, etc.
   - Export route probably has data fetches
   - Should consolidate

---

## Missing Services

From Phase 1, we identified these should exist but don't:

| Service                    | Purpose                     | Current Location               | Issue                      |
| -------------------------- | --------------------------- | ------------------------------ | -------------------------- |
| **UserRepository**         | Fetch user context, age     | Chat route                     | Scattered                  |
| **SymptomsRepository**     | Fetch/validate symptom data | Chat route + symptoms.py       | Mixed                      |
| **ConversationRepository** | Load/save conversations     | Chat route                     | Embedded                   |
| **CitationService**        | Handle citations            | Chat route                     | Complex logic not reusable |
| **PromptService**          | Build prompts               | Chat route + system_prompts.py | Not abstracted             |

---

## Testability Assessment

### Current Testability Score: 5/10

| Service        | Testable? | Why                                       |
| -------------- | --------- | ----------------------------------------- |
| `stats.py`     | 9/10      | Pure functions, no dependencies ✅        |
| `providers.py` | 8/10      | Pure functions, one external (normalizer) |
| `llm.py`       | 3/10      | Hardcoded client, can't mock              |
| `symptoms.py`  | 4/10      | Requires AsyncClient parameter            |

### Main Testing Blockers:

1. **No dependency injection** — Functions hardcode or require parameters
2. **No service classes** — Can't mock out dependencies
3. **Mixed concerns** — Data access + business logic mixed

---

## Recommendations for V2

### High Priority (Do This in V2):

1. **Create repository layer**

   ```python
   backend/app/repositories/
   ├── user_repository.py      # User context, age, etc.
   ├── symptoms_repository.py   # Symptom validation, summary cache
   ├── conversation_repository.py  # Load/save conversations
   └── provider_repository.py   # Provider queries
   ```

2. **Refactor LLM service to use dependency injection**

   ```python
   class LLMService:
       def __init__(self, client: AsyncOpenAI | None = None):
           self.client = client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
   ```

3. **Extract CitationService**
   ```python
   class CitationService:
       def sanitize_and_renumber(self, text: str, max_sources: int) -> tuple[str, list[int]]: ...
       def extract(self, text: str, chunks: list[dict]) -> list[Citation]: ...
   ```

### Medium Priority (Nice to Have):

4. **Extract PromptService**
   - Move prompt building logic to a service
   - Make it reusable by multiple endpoints

5. **Create ContextService**
   - Orchestrate user context gathering
   - Parallelize async calls

### Low Priority (Polish):

6. **Add input validation** to pure functions
7. **Extract magic numbers** to constants
8. **Consolidate LLM calls** — DRY up the three functions

---

## Service Architecture Recommendation for V2

```
backend/app/
├── repositories/          ← NEW: Data access layer
│   ├── user_repository.py
│   ├── symptoms_repository.py
│   ├── conversation_repository.py
│   └── provider_repository.py
├── services/              ← Keep: Business logic layer
│   ├── llm.py            (refactor: use DI)
│   ├── stats.py          (keep: already good)
│   ├── providers.py      (keep: already good)
│   ├── citations.py      (NEW: extract from chat route)
│   ├── context.py        (NEW: orchestrate context gathering)
│   └── prompts.py        (NEW: extract prompt building)
├── rag/                   ← Keep: RAG layer
├── api/routes/           ← Keep: Keep routes thin
└── ...
```

**Flow for Ask Meno endpoint (refactored):**

```
POST /api/chat
  ↓
ask_meno() route (30 lines)
  ├─ ContextService.get_context()              → UserRepository + SymptomsRepository
  ├─ ConversationRepository.load()
  ├─ RAGService.retrieve()
  ├─ PromptService.build()
  ├─ LLMService.generate()
  ├─ CitationService.sanitize_and_extract()
  ├─ ConversationRepository.save()
  └─ return ChatResponse
```

Each layer is testable in isolation.

---

## Summary Table

| Service                   | Quality | Testability | Reusability | Priority           |
| ------------------------- | ------- | ----------- | ----------- | ------------------ |
| stats.py                  | 9/10    | 9/10        | ✅ High     | Keep as-is         |
| providers.py              | 8/10    | 8/10        | ✅ High     | Keep as-is         |
| llm.py                    | 6/10    | 3/10        | ⚠️ Medium   | Refactor in V2     |
| symptoms.py               | 4/10    | 4/10        | ❌ Low      | Move to repository |
| **Missing:** repositories | N/A     | N/A         | ✅ High     | Create in V2       |
| **Missing:** citations    | N/A     | N/A         | ✅ High     | Extract in V2      |

---

## Key Takeaway

**Current services are good but incomplete.** You have solid pure functions (stats, providers) but:

- Missing the data access layer (repositories)
- LLM service needs dependency injection
- Citation logic should be extracted
- Chat route is doing too much

**For V2:** Build on the existing patterns, add repositories, use dependency injection consistently. You'll have a well-tested, maintainable backend.

---
