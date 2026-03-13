# Backend Code Review: V2 Standards Compliance Audit

**Date:** 2026-03-12
**Scope:** All backend Python code (`backend/app/`)
**Standards:** CLAUDE.md + `docs/dev/backend/V2CODE_EXAMPLES.md`
**Overall Compliance:** ~52%

---

## Executive Summary

The Meno backend has a **well-designed architecture on paper** (CLAUDE.md is comprehensive), but the implementation has **drifted significantly** from documented standards. Three systemic issues affect nearly every file:

1. **Domain exceptions are defined but unused** - Repositories raise `HTTPException` everywhere
2. **PII-safe logging utilities exist but aren't used** - 40% of logging statements violate safety rules
3. **Route handlers are too thick** - Three route files contain hundreds of lines of business logic

The infrastructure for doing things right exists (`app/exceptions.py`, `app/utils/logging.py`, global handlers in `main.py`). The gap is in consistent adoption.

---

## Compliance by Category

| Category | Score | Status |
|----------|-------|--------|
| Domain Exceptions | 3% | CRITICAL |
| PII-Safe Logging | 30% | CRITICAL |
| Thin Route Handlers | 55% | NEEDS WORK |
| Repository Return Types | 65% | NEEDS WORK |
| ABC Interfaces | 80% | MINOR |
| Dependency Injection | 90% | GOOD |
| Auth Centralization | 100% | EXCELLENT |
| Response Models | 95% | EXCELLENT |

---

## 1. Domain Exceptions (3% Compliant) - CRITICAL

### Standard (CLAUDE.md)

> **Rule: Never raise HTTPException in repositories or services. Only routes should know about HTTP.**

### Current State

- **64 `HTTPException` raises** found in repositories and services
- **Only 2 domain exception raises** in entire codebase (`conversation_repository.py`)
- All 5 domain exceptions in `app/exceptions.py` are effectively unused
- Global exception handlers in `main.py` (lines 30-77) are dead code

### File-by-File Violations

| File | HTTPException Raises | Domain Exception Raises |
|------|---------------------|------------------------|
| `repositories/symptoms_repository.py` | 6 | 0 |
| `repositories/appointment_repository.py` | 18 | 0 |
| `repositories/user_repository.py` | 12 | 0 |
| `repositories/providers_repository.py` | 14 | 0 |
| `repositories/conversation_repository.py` | 12 | 2 |
| `services/symptoms.py` | 2 | 0 |
| **Total** | **64** | **2** |

### Impact

- Repositories cannot be reused in background jobs, CLI scripts, or non-HTTP contexts
- The `except HTTPException: raise` anti-pattern appears throughout `appointment.py`
- Unit testing repositories requires HTTP context
- Global exception handlers never triggered

### Example Violation

```python
# appointment_repository.py (CURRENT - wrong)
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Appointment context not found",
)

# SHOULD BE:
raise EntityNotFoundError("Appointment context not found")
```

---

## 2. PII-Safe Logging (30% Compliant) - CRITICAL

### Standard (CLAUDE.md)

> Health app logs must NEVER contain personal or medical data. This includes symptom descriptions, user IDs in plaintext, user-generated content, and LLM prompt/response content.

### Current State

- **~160 total logging statements** across codebase
- **~64 statements violate PII-safe logging rules** (40% violation rate)
- **8 CRITICAL violations** log health queries or LLM responses
- Utilities exist (`hash_user_id()`, `safe_len()`, etc.) but **no route file imports them**

### Violation Categories

#### CRITICAL: Health Data Logged (8 instances)

| File | Line(s) | What's Logged |
|------|---------|---------------|
| `routes/chat.py` | 106, 112, 116-118, 123-126 | User message content (`message[:100]`) - may contain health info |
| `routes/chat.py` | 186, 189 | LLM response content (`response_text[:200]`) |
| `routes/appointment.py` | 111 | `urgent_symptom` value (health data) |
| `routes/appointment.py` | 624-637 | LLM response content (`raw_suggestions[:200]`) |

#### HIGH: Plaintext User IDs (50+ instances)

Every route file logs raw `user_id` instead of `hash_user_id(user_id)`:
- `routes/users.py` (lines 84, 102, 175-176)
- `routes/symptoms.py` (lines 172-176, 187-194, 267-273, 293-300)
- `routes/chat.py` (lines 106, 112, 168, 178, 254, 258, 268, 291)
- `routes/providers.py` (lines 198-204, 209-211)
- `routes/export.py` (lines 332-333, 351, 368, 388, 481-485)
- `routes/appointment.py` (lines 180, 392, 457, 469, 536, 682, 752, 779, 931, 1013)

#### HIGH: Email Address Logged (1 instance)

| File | Line | What's Logged |
|------|------|---------------|
| `routes/users.py` | 102 | `logger.info("User profile created: id=%s email=%s", user_id, email)` |

### What's Working

- `app/utils/logging.py` exists with all required utilities
- `docs/dev/backend/LOGGING.md` has comprehensive guidelines
- `conversation_repository.py` uses `hash_user_id()` correctly (the only file that does)

---

## 3. Thin Route Handlers (55% Compliant) - NEEDS WORK

### Standard (CLAUDE.md)

> Routes handle HTTP concerns: auth, query params, DB fetches, response formatting, error codes. Services handle business logic: calculations, transformations, data shaping.

### File-by-File Assessment

| Route File | Lines | Thickness | Compliance |
|------------|-------|-----------|------------|
| `routes/users.py` | ~180 | Medium | 60% |
| `routes/symptoms.py` | ~310 | Medium | 70% |
| `routes/providers.py` | ~360 | Thin | 75% |
| `routes/chat.py` | ~360 | **Thick** | 40% |
| `routes/export.py` | ~500 | **Thick** | 45% |
| `routes/appointment.py` | ~1433 | **Extremely Thick** | 30% |

### Worst Offenders

#### `appointment.py` - 1433 lines (30% compliant)

The most severe violation. Contains:
- **280-line** `generate_appointment_narrative` route with prompt engineering, stat calculation, LLM calls, direct DB queries
- **180-line** `_select_scenarios` helper (pure business logic)
- **140-line** `_markdown_to_pdf` / `_inline_md` helpers (rendering code)
- Direct `appointment_repo.client.table()` calls bypassing repository interface (lines 571, 760)
- System/user prompt assembly inline in route (lines 309-348)
- Reaches through service: `llm_service.provider.chat_completion()` (line 356)

#### `chat.py` - `ask_meno` route (40% compliant)

The main chat route is 140 lines containing:
- RAG retrieval and chunk deduplication (lines 93-154)
- URL parsing and fragment stripping business logic (lines 131-154)
- Inline `OpenAIProvider` instantiation bypassing DI (line 163)
- Prompt assembly (lines 156-159)
- Citation sanitization with regex (lines 186-193)
- Message persistence (lines 195-208)

#### `export.py` - PDF builder (45% compliant)

- **200+ line** `_build_pdf` function in routes file (lines 70-273)
- Direct Supabase client calls for export recording (lines 375-383, 468-476)
- Stats calculation and PDF assembly in route handler

### What's Working

- `routes/providers.py` routes are genuinely thin
- CRUD routes in `symptoms.py` are properly thin
- Conversation history routes in `chat.py` (list, get, delete) are thin
- All routes use `CurrentUser` for auth consistently

---

## 4. Repository Return Types (65% Compliant) - NEEDS WORK

### Standard (CLAUDE.md)

> Repositories MUST return typed Pydantic models, never raw dicts.

### Violations

| Repository | Method | Returns |
|-----------|--------|---------|
| `user_repository.py` | `get()` | Raw dict |
| `user_repository.py` | `update_profile()` | Raw dict |
| `providers_repository.py` | `add_to_shortlist()` | Tuple `(entry, status_code)` - repos shouldn't know about HTTP status codes |
| `conversation_repository.py` | Some methods | Raw dicts in some cases |

### What's Working

- `appointment_repository.py` returns typed models
- `symptoms_repository.py` returns typed models
- Response models on routes are consistently typed (95%+)

---

## 5. ABC Interfaces (80% Compliant) - MINOR

### Standard (CLAUDE.md)

> All repositories and services use Abstract Base Class (ABC) to define interfaces, not Protocols.

### Violation

| File | Issue |
|------|-------|
| `services/llm_base.py` | Uses `Protocol` instead of `ABC` |

All other interfaces use ABC correctly. This is a single-file fix.

---

## 6. Dependency Injection (90% Compliant) - GOOD

### What's Working

- `dependencies.py` has clean factory functions for all repos and services
- `CurrentUser` Annotated type alias is well-designed
- `get_llm_service()` handles provider selection properly
- `get_chat_service()` properly injects repo into service

### Gaps

| Issue | File | Severity |
|-------|------|----------|
| `PromptService` used as static method, not injected | `chat.py` line 157 | Medium |
| `retrieve_relevant_chunks` imported directly, not injected | `chat.py` line 109 | Medium |
| `OpenAIProvider` instantiated inline, bypassing DI | `chat.py` line 163 | High |
| Direct `SupabaseClient` in route signatures for ad-hoc queries | `appointment.py`, `export.py` | Medium |

---

## 7. Auth Centralization (100% Compliant) - EXCELLENT

- `CurrentUser` type alias used on every authenticated route
- Single auth validation point in `get_current_user_id()`
- No auth logic in route handlers
- Public endpoints (`providers/search`, `providers/states`) appropriately unauthenticated

---

## 8. Response Models (95% Compliant) - EXCELLENT

- All routes specify typed Pydantic response models
- Good use of generics for paginated responses
- OpenAPI docs auto-generated correctly

### Minor Gap

- `get_suggested_prompts` in `chat.py` returns `-> dict` instead of a typed model

---

## 9. Additional Findings

### Retry Logic

- `@retry_transient` decorator exists and is used on `OpenAIProvider.chat_completion()`
- However, when `chat.py` instantiates `OpenAIProvider` inline (line 163), it bypasses the DI system and potentially the retry-decorated service

### Global Exception Handlers

- All 5 handlers properly defined in `main.py` (lines 30-77)
- Properly map domain exceptions to HTTP status codes
- Log appropriately (though `DatabaseError` handler could potentially log sensitive query info)
- **Effectively dead code** because nothing raises domain exceptions

### Pure Functions in Route Files

Several route files contain helper functions that belong in `app/utils/` or `app/services/`:
- `users.py`: `_validate_date_of_birth()`
- `export.py`: `_log_date()`, `_build_pdf()` (200+ lines)
- `appointment.py`: `_select_scenarios()` (180 lines), `_get_scenario_category()`, `_inline_md()`, `_markdown_to_pdf()` (140 lines)

---

## Summary: Top Issues by Severity

### CRITICAL (Must Fix)

1. **All repositories raise HTTPException instead of domain exceptions** - Breaks architecture, makes repos untestable outside HTTP context, renders global handlers dead code
2. **Health data logged in chat.py and appointment.py** - User messages and LLM responses containing health info are logged; potential HIPAA/GDPR violation
3. **Plaintext user IDs logged everywhere** - 50+ instances across all route files despite `hash_user_id()` being available

### HIGH (Should Fix Soon)

4. **appointment.py is 1433 lines of business logic in a route file** - Needs extraction to `AppointmentService` and `PdfService`
5. **chat.py `ask_meno` route bypasses DI and contains 140 lines of orchestration** - Needs `AskMenoService` or similar
6. **export.py contains 200-line PDF builder in route file** - Needs `PdfService`
7. **Email logged in users.py** - Direct PII violation

### MEDIUM (Plan to Fix)

8. **User repository returns raw dicts** - Should return typed Pydantic models
9. **llm_base.py uses Protocol instead of ABC** - Single-file fix
10. **Duplicated date validation logic** in symptoms.py stats routes
11. **Direct repo.client access** in appointment.py bypasses repository interface
12. **Provider repository returns (entry, status_code) tuple** - Should use domain exception for conflicts
