# Backend Refactoring Plan: V2 Standards Compliance

**Date:** 2026-03-12
**Based on:** `BACKEND_CODE_REVIEW.md` audit findings
**Goal:** Bring backend from ~52% to 90%+ V2 compliance
**Estimated Total Effort:** 4-5 focused sessions

---

## Phase 1: Domain Exceptions Migration (Foundation)

**Priority:** CRITICAL - Unblocks everything else
**Effort:** 1 session
**Impact:** 3% -> 95% domain exception compliance

Everything downstream depends on this. Until repositories raise domain exceptions, global handlers are dead code, routes can't catch properly, and repos are untestable outside HTTP context.

### 1.1 Migrate All Repositories to Domain Exceptions

**Files to modify (in order):**

| File                                      | HTTPException Raises | Key Changes                                                                                             |
| ----------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------- |
| `repositories/symptoms_repository.py`     | 6                    | Replace with `EntityNotFoundError`, `DatabaseError`, `ValidationError`                                  |
| `repositories/user_repository.py`         | 12                   | Replace with `EntityNotFoundError`, `DatabaseError`                                                     |
| `repositories/conversation_repository.py` | 12                   | Already has 2 correct; fix remaining 12                                                                 |
| `repositories/providers_repository.py`    | 14                   | Replace with `EntityNotFoundError`, `DatabaseError`; add `DuplicateEntityError` for shortlist conflicts |
| `repositories/appointment_repository.py`  | 18                   | Replace with `EntityNotFoundError`, `DatabaseError`                                                     |

**Pattern for each:**

```python
# BEFORE
from fastapi import HTTPException, status
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

# AFTER
from app.exceptions import EntityNotFoundError, DatabaseError
raise EntityNotFoundError("Appointment context not found")
```

**Mapping:**

- `404` -> `EntityNotFoundError`
- `500` -> `DatabaseError`
- `400` -> `ValidationError`
- `409` (shortlist conflict) -> New `DuplicateEntityError` (add to `app/exceptions.py`)

### 1.2 Migrate services/symptoms.py

This service raises `HTTPException` directly (2 instances). Convert to `ValidationError` / `DatabaseError`.

### 1.3 Update Route Exception Handling

After repos raise domain exceptions, routes that currently catch `HTTPException` from repos need updating:

```python
# BEFORE (appointment.py pattern)
try:
    context = await appointment_repo.get_context(...)
except HTTPException:
    raise
except Exception as exc:
    raise HTTPException(500, ...)

# AFTER (let global handlers catch, or explicit conversion)
try:
    context = await appointment_repo.get_context(...)
except EntityNotFoundError:
    raise  # Global handler converts to 404
except DatabaseError:
    raise  # Global handler converts to 500
```

Most routes can simply **let domain exceptions propagate** to global handlers.

### 1.4 Add DuplicateEntityError to exceptions.py

```python
class DuplicateEntityError(MenoBaseError):
    """Entity already exists (e.g., duplicate shortlist entry)."""
    pass
```

Add handler in `main.py`:

```python
@app.exception_handler(DuplicateEntityError)
async def duplicate_entity_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
```

### 1.5 Update Tests

Existing repository tests that assert `HTTPException` raises need updating to assert domain exceptions. Most tests use `pytest.raises(HTTPException)` which becomes `pytest.raises(EntityNotFoundError)` etc.

### Verification

- All repository files: `grep -r "HTTPException" backend/app/repositories/` returns 0
- All service files: `grep -r "HTTPException" backend/app/services/` returns 0
- `uv run pytest` passes with no regressions

---

## Phase 2: PII-Safe Logging (Compliance)

**Priority:** CRITICAL - Legal/compliance risk
**Effort:** 1 session
**Impact:** 30% -> 95% logging compliance

### 2.1 Fix CRITICAL Health Data Logging (8 instances)

**Do first - these are the most dangerous:**

| File                    | Line(s)                    | Current                 | Fix                                   |
| ----------------------- | -------------------------- | ----------------------- | ------------------------------------- |
| `routes/chat.py`        | 106, 112, 116-118, 123-126 | `message[:100]`         | `safe_len(message)` chars             |
| `routes/chat.py`        | 186, 189                   | `response_text[:200]`   | `safe_len(response_text)` chars       |
| `routes/appointment.py` | 111                        | `urgent_symptom` value  | Remove or log "has_urgent=True/False" |
| `routes/appointment.py` | 624-637                    | `raw_suggestions[:200]` | `safe_len(raw_suggestions)` chars     |

### 2.2 Replace All Plaintext user_id Logging (~50 instances)

Add import to every route file:

```python
from app.utils.logging import hash_user_id
```

Then find/replace pattern:

```python
# BEFORE
logger.info("... user=%s ...", user_id)

# AFTER
logger.info("... user=%s ...", hash_user_id(user_id))
```

**Files:** `users.py`, `symptoms.py`, `chat.py`, `providers.py`, `export.py`, `appointment.py`

### 2.3 Remove Email Logging

`routes/users.py` line 102:

```python
# BEFORE
logger.info("User profile created: id=%s email=%s", user_id, email)

# AFTER
logger.info("User profile created: user=%s", hash_user_id(user_id))
```

### 2.4 Add safe_len() to LLM Call Logging

Any logging near LLM calls should use `safe_len()` for content:

```python
logger.debug("LLM call: %d input chars", safe_len(prompt))
logger.debug("LLM response: %d chars", safe_len(response_text))
```

### Verification

- `grep -rn "user_id" backend/app/api/routes/` should show only hashed usage
- `grep -rn "message\[:" backend/app/api/routes/` returns 0
- `grep -rn "response_text\[:" backend/app/api/routes/` returns 0
- `grep -rn "email" backend/app/api/routes/users.py` shows no logging of email

---

## Phase 3: Extract Thick Routes to Services

**Priority:** HIGH - Architecture compliance
**Effort:** 2 sessions
**Impact:** 55% -> 85% thin route compliance

### 3.1 Create AppointmentService (Session 1)

**Current:** `appointment.py` is 1433 lines. Routes contain prompt engineering, scenario selection, stat calculation, PDF rendering, direct DB queries.

**Target:** Route becomes thin wrapper calling service methods.

**New file:** `app/services/appointment.py`

**Methods to extract:**

| Method                 | Source Lines | What It Does                                                         |
| ---------------------- | ------------ | -------------------------------------------------------------------- |
| `generate_narrative()` | 135-415      | Fetch context + logs, calculate stats, build prompts, call LLM, save |
| `generate_scenarios()` | ~420-670     | Fetch context + narrative, call LLM for scenarios, parse JSON, save  |
| `select_scenarios()`   | 1077-1255    | Business logic for scenario selection based on symptoms              |
| `generate_pdf()`       | ~700-950     | Orchestrate PDF content generation (summary, questions, cheatsheet)  |

**Move helpers to appropriate locations:**

- `_select_scenarios()`, `_get_scenario_category()` -> `app/services/appointment.py` (business logic)
- `_inline_md()`, `_markdown_to_pdf()` -> `app/services/pdf.py` (rendering)
- Prompt assembly -> `app/services/prompt.py` or within `AppointmentService`

**Eliminate direct DB access in routes:**

- `appointment_repo.client.table()` calls (lines 571, 760) -> New repository methods
- `client.table("symptoms_reference")` (line 250) -> `symptoms_repo.get_reference()`

**Route after refactor:**

```python
@router.post("/{appointment_id}/narrative")
async def generate_appointment_narrative(
    appointment_id: str,
    payload: GenerateNarrativeRequest,
    user_id: CurrentUser,
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentPrepNarrativeResponse:
    return await service.generate_narrative(appointment_id, user_id, payload)
```

### 3.2 Create AskMenoService (Session 1)

**Current:** `chat.py` `ask_meno` route is 140 lines with RAG, LLM, citations, persistence.

**New file:** `app/services/ask_meno.py` (or extend `app/services/chat.py`)

**Methods to extract:**

| Method                  | What It Does                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| `ask()`                 | Orchestrate: RAG retrieval -> prompt assembly -> LLM call -> citation processing -> persistence |
| `_deduplicate_chunks()` | URL dedup with fragment stripping                                                               |
| `_sanitize_citations()` | Regex-based citation cleanup                                                                    |

**Fix DI violations:**

- Remove inline `OpenAIProvider(api_key=...)` - use injected `llm_service`
- Inject `retrieve_relevant_chunks` via DI or pass as dependency to service

### 3.3 Create PdfService (Session 2)

**Current:** `export.py` has 200-line `_build_pdf()` in route file. `appointment.py` has `_markdown_to_pdf()`.

**New file:** `app/services/pdf.py`

**Consolidate all PDF rendering:**

- `_build_pdf()` from export.py
- `_markdown_to_pdf()` / `_inline_md()` from appointment.py
- Shared styling constants

### 3.4 Create ExportService (Session 2)

**Current:** Export routes do stats calculation, PDF building, CSV building, and direct DB calls.

**New file:** `app/services/export.py`

**Methods:**

- `export_pdf()` - orchestrate data fetch, stats, LLM calls, PDF build, record export
- `export_csv()` - orchestrate data fetch, transformation, CSV build, record export

**Move export recording to repository:**

- Direct `client.table("exports").insert()` calls -> `export_repository.record_export()`

### 3.5 Move Helper Functions to Utils

| Function                    | Current Location   | New Location                                   |
| --------------------------- | ------------------ | ---------------------------------------------- |
| `_validate_date_of_birth()` | `routes/users.py`  | `app/utils/dates.py` (raise `ValidationError`) |
| `_log_date()`               | `routes/export.py` | `app/utils/dates.py`                           |

### 3.6 Update Dependencies

Add to `app/api/dependencies.py`:

```python
def get_appointment_service(...) -> AppointmentService: ...
def get_ask_meno_service(...) -> AskMenoService: ...
def get_export_service(...) -> ExportService: ...
def get_pdf_service(...) -> PdfService: ...
```

### Verification

- `appointment.py` < 200 lines
- `chat.py` `ask_meno` route < 30 lines
- `export.py` routes < 30 lines each
- No `_build_pdf`, `_select_scenarios`, etc. in route files
- No `repo.client.table()` calls in route files
- `uv run pytest` passes

---

## Phase 4: Remaining Fixes (Polish)

**Priority:** MEDIUM
**Effort:** 0.5 session
**Impact:** Various compliance improvements

### 4.1 Fix llm_base.py: Protocol -> ABC

```python
# BEFORE
from typing import Protocol
class LLMProvider(Protocol): ...

# AFTER
from abc import ABC, abstractmethod
class LLMProvider(ABC): ...
```

### 4.2 Repository Return Types

Update `user_repository.py` to return Pydantic models:

- `get()` -> return `UserProfile` model
- `update_profile()` -> return `UserProfile` model

Update `providers_repository.py`:

- `add_to_shortlist()` -> return `ShortlistEntry` model, raise `DuplicateEntityError` for conflicts instead of returning status code

### 4.3 Minor Route Fixes

- `chat.py`: Type `get_suggested_prompts` return as Pydantic model instead of `-> dict`
- `symptoms.py`: Deduplicate date validation logic into shared utility
- `providers.py`: Move `provider_name.strip()` validation to Pydantic model validator
- `appointment.py`: Replace `if limit > 100: limit = 100` with `Query(ge=1, le=100)`

### 4.4 Dependencies Cleanup

- Add `PromptService` to DI if used as injected dependency
- Add RAG retrieval to DI (or inject via service constructor)

### Verification

- `grep -r "Protocol" backend/app/services/` returns 0
- `user_repository.py` type hints show Pydantic model returns
- `uv run pytest` passes

---

## Phase Summary

| Phase                | Focus        | Effort      | Compliance Impact |
| -------------------- | ------------ | ----------- | ----------------- |
| 1. Domain Exceptions | Foundation   | 1 session   | 52% -> 65%        |
| 2. PII-Safe Logging  | Compliance   | 1 session   | 65% -> 75%        |
| 3. Extract Services  | Architecture | 2 sessions  | 75% -> 90%        |
| 4. Polish            | Cleanup      | 0.5 session | 90% -> 95%        |

### Recommended Order

**Phase 1 must come first** - domain exceptions are the foundation that routes, services, and tests all depend on.

**Phase 2 can be done independently** - logging changes are safe, isolated edits.

**Phase 3 is the bulk of the work** - but each service extraction is independent. Start with `AppointmentService` (biggest impact) then `AskMenoService`, then `PdfService`/`ExportService`.

**Phase 4 is optional polish** - do whenever convenient.

---

## Risk Assessment

| Risk                                             | Mitigation                                                                     |
| ------------------------------------------------ | ------------------------------------------------------------------------------ |
| Domain exception migration breaks existing tests | Update tests in same PR; they assert on exception types                        |
| Service extraction introduces bugs               | Extract method-by-method with tests; routes call service, verify same behavior |
| Logging changes miss instances                   | Use `grep` verification commands listed above                                  |
| Large PRs are hard to review                     | Each phase is a separate PR; Phase 3 can be split per service                  |

---

## Definition of Done (per phase)

- [ ] All `uv run pytest` tests pass
- [ ] Coverage doesn't drop below 80%
- [ ] `grep` verification commands pass
- [ ] No new `HTTPException` in repositories or services
- [ ] No plaintext user_id in logging
- [ ] Route files contain only route handlers and imports
