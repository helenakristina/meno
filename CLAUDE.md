# CLAUDE.md - Development Context for Meno

**⚠️ IMPORTANT: DEV-ONLY POC**

Meno is currently a proof-of-concept running locally only. It is NOT deployed to production.
Before any real users access Meno, the following must be completed:

1. ✅ Medical advice boundary tested (GUARDRAILS_AUDIT.md)
2. ⏳ Legal review (LEGAL_PREP.md — awaiting attorney)
3. ⏳ Job + API cost plan (6 months)
4. ⏳ Production deployment checklist (PRODUCTION_CHECKLIST.md)

This document describes the architecture and patterns. See PRODUCTION_CHECKLIST.md for the path to launch.

**Last Updated:** February 2026  
**Project Status:** Active Development - V1 Phase

---

## Project Overview

**Meno** is a web application that helps women navigate perimenopause and menopause with clarity, evidence-based information, and compassionate support.

**Core Mission:** Your symptoms are real. You don't have to just live with it. Help is available.

**What Meno Is:**

- A personal symptom tracking tool
- An educational resource grounded in current research
- A pattern recognition assistant using LLM technology
- A provider discovery tool
- A bridge between patients and informed healthcare conversations

**What Meno Is NOT:**

- A diagnostic tool
- A treatment recommendation engine
- A replacement for medical advice
- A medication management system (V1)

**Key Constraint:** We never cross the line into medical advice. We provide information and pattern recognition, not diagnosis or treatment recommendations.

---

## Tech Stack

### Frontend

- **SvelteKit 2.x** with TypeScript
- **Svelte 5** (using runes: `$state`, `$derived`, `$effect`, `$props`)
- **Tailwind CSS 4.x** for styling
- **shadcn-svelte** for UI components
- **Supabase client** (`@supabase/supabase-js`, `@supabase/ssr`) for auth and data
- **Node 25+**

**Important Svelte 5 Conventions:**

- Use `let { children } = $props()` and `{@render children()}` instead of `<slot />`
- Use `onclick={}` instead of `on:click={}`
- Use `$state()` for reactive variables
- Import from `$app/state` not `$app/stores` (page rune)

### Backend

- **FastAPI** (Python 3.11+) with async/await throughout
- **uv** for Python dependency management
- **Supabase** (PostgreSQL 15+) for database
- **pgvector** extension for RAG embeddings
- **Anthropic API** (Claude Sonnet 4) for LLM features
- **OpenAI API** (text-embedding-3-small) for embeddings in production
- **sentence-transformers** for embeddings in local development

### Infrastructure

- **Vercel** - Frontend hosting (auto-deploy from main branch)
- **Railway** - Backend hosting (auto-deploy from main branch)
- **Supabase** - Database, auth, and storage
- **GitHub** - Version control

---

## Repository Structure

```
meno/
├── README.md
├── CLAUDE.md              ← You are here
├── .gitignore
├── docs/
│   └── dev/
│       └── DESIGN.md      ← Comprehensive design document
├── frontend/              ← SvelteKit application
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/ui/  ← shadcn-svelte components
│   │   │   ├── supabase/
│   │   │   │   └── client.ts
│   │   │   └── stores/
│   │   │       └── auth.ts
│   │   └── routes/
│   │       ├── (auth)/         ← No navigation group
│   │       │   ├── login/
│   │       │   └── onboarding/
│   │       ├── (app)/          ← With navigation group
│   │       │   ├── dashboard/
│   │       │   ├── log/
│   │       │   ├── ask/
│   │       │   ├── providers/
│   │       │   └── export/
│   │       └── practice/       ← Practice/learning pages
│   ├── package.json
│   └── .env                    ← Never commit (gitignored)
└── backend/               ← FastAPI application
    ├── app/
    │   ├── main.py           ← FastAPI app entry point
    │   ├── core/
    │   │   ├── config.py     ← Settings with pydantic-settings
    │   │   └── supabase.py
    │   ├── api/
    │   │   └── routes/       ← API endpoints
    │   ├── models/           ← Pydantic models
    │   ├── services/         ← Business logic
    │   └── rag/              ← RAG pipeline code
    ├── pyproject.toml
    └── .env                  ← Never commit (gitignored)
```

---

## Database Schema

**Full schema documented in:** `docs/dev/DESIGN.md` (Section 9: Data Models)

**Key Tables:**

- `users` - User profiles, references auth.users
- `symptom_logs` - Daily symptom entries
- `symptoms_reference` - Master list of 34 symptoms (public reference data)
- `symptom_summary_cache` - Pre-computed summaries for LLM context
- `conversations` - Ask Meno chat history (JSONB)
- `providers` - Healthcare provider directory (public data)
- `exports` - Export history (immutable audit trail)
- `rag_documents` - Knowledge base with vector embeddings

**Security:** All user-data tables have Row Level Security (RLS) enabled. Users can only access their own data at the database level via `auth.uid()` policies.

**Reference Data:** `symptoms_reference` and `providers` have no RLS - everyone sees the same data.

---

## Code Standards

### Python (Backend)

**Style:**

- Use `ruff` for linting and formatting (already configured)
- Type hints on all function signatures
- Async/await throughout - FastAPI is async-first
- Docstrings for all public functions (Google style)

**Error Handling: Domain Exceptions Pattern**

**Rule: Never raise HTTPException in repositories or services. Only routes should know about HTTP.**

Use domain exceptions from `app.exceptions`:

```
MenoBaseError (base)
├── EntityNotFoundError (404) - Resource not found or doesn't belong to user
├── DatabaseError (500) - Database operation failed
├── ValidationError (400) - Input/business rule validation failed
├── UnauthorizedError (401) - User not authenticated
└── PermissionError (403) - User authenticated but not authorized
```

**Pattern: Repository Layer**

```python
from app.exceptions import EntityNotFoundError, DatabaseError

async def get_context(self, appointment_id: str, user_id: str) -> AppointmentContext:
    """Fetch appointment context.

    Raises:
        EntityNotFoundError: Appointment not found or doesn't belong to user.
        DatabaseError: Database operation failed.
    """
    try:
        response = await self.client.table("appointment_prep_contexts").select("*").execute()
        if not response.data:
            raise EntityNotFoundError(f"Appointment {appointment_id} not found")
        return AppointmentContext(**response.data[0])
    except EntityNotFoundError:
        raise  # Re-raise domain exceptions
    except Exception as e:
        raise DatabaseError(f"Failed to fetch context: {e}") from e
```

**Pattern: Route Layer**

Global exception handlers in `main.py` automatically convert domain exceptions to HTTP responses. Routes can leverage them:

```python
from app.exceptions import EntityNotFoundError

@router.post("/appointment-prep/context")
async def create_appointment_context(
    payload: CreateAppointmentContextRequest,
    user_id: CurrentUser,
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
) -> CreateAppointmentContextResponse:
    """Create appointment context.

    Domain exceptions are caught by global handlers:
    - EntityNotFoundError → 404
    - DatabaseError → 500
    - ValidationError → 400
    """
    appointment_id = await appointment_repo.save_context(user_id, context)
    return CreateAppointmentContextResponse(appointment_id=appointment_id, next_step="narrative")
```

Or explicit handling in route when custom logic needed:

```python
from app.exceptions import EntityNotFoundError
from fastapi import HTTPException

try:
    result = await appointment_repo.get_context(appointment_id, user_id)
except EntityNotFoundError:
    raise HTTPException(status_code=404, detail="Appointment not found")
```

**Benefits:**

- **Testable:** Services work without HTTP context (routes, background jobs, scripts)
- **Reusable:** Same code across different contexts
- **Clean separation:** Each layer has clear concerns
- **Maintainable:** Exception mapping is centralized in global handlers

**Repository Return Types: Use Pydantic Models**

**Rule: Repositories MUST return typed Pydantic models, never raw dicts.**

**Why Pydantic Models?**

- **Type safety:** IDE knows what fields exist, autocomplete works
- **Validation:** Pydantic validates data shape and types on construction
- **Self-documenting:** Model definition shows exact expected structure
- **Reduces bugs:** Type checker catches missing/wrong field access
- **Claude Code generation:** Claude learns from examples; showing models produces better code

**Pattern: Model Return Types**

Define a Pydantic model for each entity the repository returns:

```python
# backend/app/models/user.py

from pydantic import BaseModel

class UserContext(BaseModel):
    """User journey and demographic context."""
    journey_stage: str = "exploration"
    age: int | None = None
```

Then return it from repository:

```python
# backend/app/repositories/user_repository.py

from app.models.user import UserContext

class UserRepository:
    async def get_context(self, user_id: str) -> UserContext:
        """Fetch user's journey stage and age.

        Returns:
            UserContext with journey_stage and age (age may be None if DOB not set).

        Raises:
            EntityNotFoundError: User not found.
            DatabaseError: Database query failed.
        """
        try:
            response = (
                await self.client.table("user_profiles")
                .select("journey_stage, date_of_birth")
                .eq("id", user_id)
                .single()
                .execute()
            )

            if not response.data:
                raise EntityNotFoundError(f"User {user_id} not found")

            data = response.data
            age = None
            if data.get("date_of_birth"):
                try:
                    age = calculate_age(data["date_of_birth"])
                except ValueError:
                    logger.warning("Invalid DOB for user %s", user_id)

            # Return typed model, not dict
            return UserContext(
                journey_stage=data.get("journey_stage", "exploration"),
                age=age,
            )

        except EntityNotFoundError:
            raise
        except Exception as exc:
            logger.error("Failed to fetch user context: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to fetch user context: {exc}") from exc
```

**Benefits in Practice**

```python
# With models (better)
context = await user_repo.get_context(user_id)
print(context.journey_stage)  # IDE autocomplete works
print(context.age)  # Type checker knows it's int | None
# Can't get field name wrong
```

**Pydantic Model Best Practices**

```python
# ✅ GOOD: Clear, typed, documented

class AppointmentContext(BaseModel):
    """Appointment prep context from Step 1."""
    appointment_type: str
    goal: str
    dismissed_before: str
    urgent_symptom: str | None = None


# ✅ GOOD: Optional fields with defaults

class UserContext(BaseModel):
    journey_stage: str = "exploration"  # Default value
    age: int | None = None  # Explicitly optional
```

**When to Create Models**

Create a model when:
- Repository returns multiple fields (not just an ID or single value)
- Those fields are used together across services/routes
- The structure is stable (unlikely to change per-request)

Examples:
- ✅ UserContext (journey_stage + age)
- ✅ AppointmentContext (type + goal + dismissal + urgent symptom)
- ✅ SymptomLog (id + date + symptoms + notes)
- ❌ Single value like user_id or count (just use the primitive type)

**Testing:**

- Use `pytest` with `pytest-asyncio`
- Test files mirror source structure: `tests/api/routes/test_symptoms.py`
- Mock external services (Supabase, Anthropic, OpenAI)
- Aim for >70% coverage on business logic

**Logging:**

- Use Python's standard `logging` module
- Log levels: DEBUG (development), INFO (key events), WARNING (recoverable issues), ERROR (failures)
- Include request IDs in logs for tracing
- Never log sensitive data (passwords, API keys, health data)

**Retry & Resilience Patterns**

**Rule: All external API calls must have retry logic. Use `@retry_transient` decorator.**

External services (OpenAI, Supabase, etc.) can fail transiently:
- Rate limits (429 Too Many Requests) — common when processing lots of LLM calls
- Timeouts — network latency, service load
- Connection errors — temporary network issues

For critical user flows (appointment prep), a single transient failure causes hard errors. Retry logic makes the app resilient.

**Pattern: Use @retry_transient Decorator**

```python
from app.utils.retry import retry_transient

class OpenAIProvider(LLMProvider):
    @retry_transient(max_attempts=3, initial_wait=1, max_wait=10)
    async def chat_completion(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Call OpenAI API with automatic retry on transient failures.

        Automatically retries on:
        - Timeouts (network latency)
        - Rate limits (429)
        - Connection errors

        Does NOT retry on:
        - Auth errors (401) — permanent
        - Not found (404) — permanent
        - Bad request (400) — permanent
        """
        response = await self.client.chat.completions.create(...)
        return response.choices[0].message.content
```

**Behavior:**
- **Max attempts:** 3 attempts by default (customizable)
- **Exponential backoff:** Wait 1s, then 2s, then 4s between attempts
- **Smart retry:** Only retries transient errors (timeouts, rate limits, connection errors)
- **Doesn't retry:** Auth errors (401), not found (404), bad request (400)
- **Logging:** Each retry attempt logged as warning
- **Reraises:** If all retries fail, exception re-raised to caller

**Customizing Retry Behavior:**

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

**When NOT to Retry:**

Do NOT add retry logic to:
- Database queries (Supabase RLS enforcement happens at connection time)
- Auth checks (401 is permanent, no point retrying)
- Pydantic validation (400 is permanent)

**Default:** Only decorate external API calls (OpenAI, Claude, etc.)

See `app/utils/retry.py` for implementation details and `is_retryable_exception()` logic.

### TypeScript (Frontend)

**Style:**

- Use TypeScript strict mode
- Svelte 5 runes for reactivity (`$state`, `$derived`, `$effect`)
- Prefer functional components
- Use Tailwind utility classes, avoid custom CSS unless necessary

**Error Handling:**

- Try/catch on all async operations
- Show user-friendly error messages in UI
- Log errors to console in development
- Consider Sentry or similar for production error tracking (V2)

**Key Patterns:**

```typescript
let loading = $state(false);
let error = $state("");

async function handleSubmit() {
  loading = true;
  error = "";

  try {
    const { data, error: apiError } = await supabase.from("table").select();

    if (apiError) throw apiError;

    // Success path
  } catch (e) {
    error = e.message;
    console.error("Operation failed:", e);
  } finally {
    loading = false;
  }
}
```

### Responsive Design Standards

**Mobile-First Approach:**

- Design for 375px (mobile) first, then enhance for larger viewports
- Test at 375px, 667px (landscape), 768px (tablet), 1440px (desktop)
- No horizontal scroll at any viewport size

**Tailwind Breakpoints:**

```
sm: 640px   (tablet portrait)
md: 768px   (tablet landscape)
lg: 1024px  (desktop)
```

**Key Rules:**

- Always use `w-full max-w-full` on main containers
- Use `px-4 sm:px-6 lg:px-8` for responsive padding
- Wrap flex/grid layouts: `flex flex-col sm:flex-row`
- All interactive elements minimum 44×44px (`min-h-11`)
- Navigation must collapse to hamburger on mobile
- No buttons hidden on hover (breaks mobile UX)

**Pitfalls to Avoid:**

- ❌ Fixed widths on containers
- ❌ Non-responsive padding
- ❌ Absolute positioned elements going off-screen
- ❌ Interactive elements < 44px
- ❌ Nav bars that don't collapse
- ❌ Hover-only buttons

**Testing:**

```bash
# In DevTools: Ctrl+Shift+M for device toolbar
# Test at: 375px, 667px, 768px, 1440px
# Verify: no horizontal scroll, all buttons tappable
```

### Accessibility Standards (WCAG 2.1 Level AA)

**Keyboard Navigation:**

- All interactive elements accessible via Tab/Enter/Escape/Arrow keys
- Focus indicator always visible (never `outline: none` without replacement)
- Dropdowns support ↑↓ navigation, Escape to close
- No keyboard traps

**Touch Targets:**

- Minimum 44×44px for all interactive elements
- Use `min-h-11` for buttons, `h-11` for inputs
- Helps both touch users AND keyboard users

**Color Contrast:**

- Normal text: 4.5:1 ratio
- Large text (18px+): 3:1 ratio

**Semantic HTML:**

- Use `<button>` not `<div>` for clickable actions
- Use `<nav>`, `<main>`, `<section>` for regions
- Use `<h1>`, `<h2>`, etc. in proper hierarchy
- Form inputs must have `<label for="id">`

**ARIA Labels:**

- `aria-label` for icon-only buttons
- `aria-labelledby` for sections linked to headings
- `aria-describedby` for inputs with error messages
- `aria-current="page"` for current navigation
- `aria-expanded` for expandable sections
- `aria-controls` to link buttons to elements

**Focus Management:**

- Auto-focus on modals
- Return focus to trigger element when closing
- Use `aria-live="polite"` for dynamic content announcements
- Use `aria-busy` for loading states

**Form Validation:**

- Error messages associated via `aria-describedby`
- Required fields marked `aria-required="true"`
- Validation on blur, not keydown

**Images & Icons:**

- Meaningful images: `alt="descriptive text"`
- Decorative: `alt=""` or `aria-hidden="true"`
- Icon-only buttons: `aria-label="action"`

### Accessibility + Responsiveness Integration

Build accessibility and responsiveness in from the start, not as separate passes. They are interconnected:

- **Focus visibility:** Must be visible at all viewport sizes (not just hover)
- **Touch targets:** 44px rule helps both touch AND keyboard users
- **Hover-only interactions:** Break mobile UX AND accessibility
- **Screen readers:** Must work at all breakpoints
- **Text readability:** Minimum 14px on mobile, scale appropriately
- **Color contrast:** Must meet WCAG AA at all viewport sizes and zoom levels

## **Key Principle:** If something works on mobile (375px) with keyboard navigation, it's accessible. If it's inaccessible, it's usually broken on mobile too.

## Documentation Standards

### When to Write Docstrings

**Write docstrings when they add information the code doesn't already convey.**

**✅ Always document:**

- Public API endpoints (what they do, params, returns, raises)
- Complex business logic (co-occurrence calculation, pattern analysis)
- LLM integration points (prompt assembly, RAG retrieval, anonymization)
- Non-obvious caching or performance optimizations
- Anything where the "why" matters more than the "what"

**Example - Good docstring:**

```python
async def calculate_symptom_cooccurrence(logs: list[SymptomLog]) -> dict[tuple[str, str], float]:
    """
    Calculate co-occurrence rates between all symptom pairs.

    Returns a dict mapping symptom pairs to their co-occurrence percentage.
    Example: {('fatigue', 'brain_fog'): 0.78} means they occurred together 78% of the time.

    Used by the dashboard to show "symptoms that travel together" insight card.
    """
```

**❌ Skip docstrings for:**

- Self-explanatory functions (name + types say it all)
- Simple CRUD operations
- Test functions (use descriptive test names instead: `test_X_when_Y_then_Z`)
- Pydantic models (fields are self-documenting)
- Private helper functions only called internally

**Example - No docstring needed:**

```python
async def get_user(user_id: str) -> User:
    # Name and types are clear, no docstring needed
    return await supabase.from_("users").select("*").eq("id", user_id).execute()
```

### Test Documentation

**Use descriptive test names instead of docstrings:**

```python
# Good - test name is self-documenting
async def test_create_symptom_log_returns_401_when_missing_auth():
    ...

# Bad - unnecessary docstring
async def test_auth():
    """Test that endpoint requires authentication."""  # Redundant
    ...
```

**Group related tests with comments when helpful:**

```python
# Authentication tests
async def test_create_log_requires_valid_token():
    ...

async def test_create_log_rejects_expired_token():
    ...

# Validation tests
async def test_create_log_requires_at_least_one_symptom():
    ...
```

### Code Comments

**Use comments sparingly for "why" not "what":**

```python
# Good - explains why
# We cache summaries for 24 hours because regenerating them on every
# Ask Meno query would cost ~$0.02 per query and slow response time
cache_ttl = 86400

# Bad - restates the code
# Set cache TTL to 86400 seconds
cache_ttl = 86400
```

---

## Architecture Patterns

### Backend Service Layer

Business logic lives in `backend/app/services/`, separate from route handlers.

**Stats calculations** — `backend/app/services/stats.py`:

- `calculate_frequency_stats(logs, symptoms_reference)` → `list[SymptomFrequency]`
- `calculate_cooccurrence_stats(logs, symptoms_reference, min_threshold=2)` → `list[SymptomPair]`
- `MAX_COOCCURRENCE_PAIRS = 10` — cap exported as a constant so tests can reference it

**Division of responsibilities:**

- **Routes** handle HTTP concerns: auth, query params, DB fetches, response formatting, error codes
- **Services** handle business logic: calculations, transformations, data shaping — no DB access
- **Services are pure functions** — stateless, no side effects, easy to unit-test

**Testing services directly** — `backend/tests/services/`:

```python
# No mocking needed — pass constructed dicts, assert on returned models
from app.services.stats import calculate_frequency_stats

def test_counts_sorted_descending():
    logs = [{"symptoms": ["id-a", "id-b"]}, {"symptoms": ["id-a"]}]
    ref = {"id-a": {"name": "Hot flashes", "category": "vasomotor"}, ...}
    stats = calculate_frequency_stats(logs, ref)
    assert stats[0].symptom_id == "id-a"
    assert stats[0].count == 2
```

### Business Logic Utilities

**Rule: Shared business logic should live in `app/utils/`, not scattered across repositories or services.**

#### What Goes in Utils

Business logic that's used by multiple layers:
- Date calculations (age, date ranges, formatting)
- Statistical calculations (frequency, co-occurrence analysis)
- Data transformations
- Validation helpers
- Formatting utilities

#### What Stays in Repositories/Services

- Data access queries (repositories only)
- Service orchestration — calling multiple repos/utils together (services only)
- API request handling (routes only)

#### Pattern: Utils in Action

**Date utilities example:**

```python
# app/utils/dates.py - Shared across all layers

from app.utils.dates import calculate_age, get_date_range

# In repository
age = calculate_age(user_dob)
start, end = get_date_range(60)

# In service
age = calculate_age(user_dob)
start, end = get_date_range(90)
```

**Stats utilities example:**

```python
# app/utils/stats.py - Pure calculations, no DB access

from app.utils.stats import calculate_frequency_stats, calculate_cooccurrence_stats

# In appointment prep service (narrative generation)
freq_stats = calculate_frequency_stats(logs, symptoms_ref)
coocc_stats = calculate_cooccurrence_stats(logs, symptoms_ref)
prompt = self._build_prompt(freq_stats, coocc_stats)
narrative = await self.provider.chat_completion(...)

# In future cycle analysis feature
freq_stats = calculate_frequency_stats(logs, symptoms_ref)
patterns = analyze_cycles(freq_stats)
```

**Available utilities:**

*Dates:*
- `calculate_age(date_of_birth: str) -> int` — Age from ISO date string
- `get_date_range(days_back: int) -> tuple[date, date]` — Date range for past N days (1-365)
- `is_valid_iso_date(date_string: str) -> bool` — Validate ISO date format
- `iso_date_to_display(iso_date: str) -> str` — Convert ISO date to human-readable
- `days_since(iso_date: str) -> int` — Days elapsed since a date

*Statistics:*
- `calculate_frequency_stats(logs: list[dict], symptoms_reference: dict) -> list[SymptomFrequency]` — Per-symptom counts
- `calculate_cooccurrence_stats(logs: list[dict], symptoms_reference: dict) -> list[SymptomPair]` — Symptom pair co-occurrence rates

#### Benefits

- **DRY:** Single source of truth for calculations
- **Testable:** Business logic tested independently (no DB mocks needed)
- **Reusable:** Works across repositories, services, background jobs, CLI scripts
- **Maintainable:** Changes to logic in one place
- **Clear separation:** Each layer has clear responsibilities

#### When You Add New Business Logic

1. Does it need to be used by multiple repositories/services?
   - YES → Create in `app/utils/`
   - NO → Keep it where it's used

2. Is it a calculation, transformation, or formatting?
   - YES → Belongs in utils
   - NO → Might belong in service layer

3. Can it be tested independently?
   - YES (easier to test as util)
   - NO (might be too tightly coupled, reconsider design)

---

### Frontend API Client

All backend API calls go through `frontend/src/lib/api/client.ts`. Never call `fetch()` directly for backend requests.

**Import and use:**

```typescript
import { apiClient } from "$lib/api/client";

// GET with query params
const data = await apiClient.get<{ logs: Log[] }>("/api/symptoms/logs", {
  start_date: "2026-01-01",
  limit: 50,
});

// POST with body
await apiClient.post("/api/symptoms/logs", {
  symptoms: ["id-a"],
  source: "cards",
});

// File download
const blob = await apiClient.get(
  "/api/export/pdf",
  {},
  { responseType: "blob" },
);
```

**What the client handles automatically:**

- Auth token from `supabase.auth.getSession()` — throws `"Not authenticated"` if missing
- `Authorization: Bearer <token>` header on every request
- `Content-Type: application/json` for POST/PUT
- Error body parsing — surfaces `detail` field from FastAPI error responses
- Network errors — throws `"Network error. Please check your connection..."`

**What callers handle:**

- Catching errors and setting `error` state for display
- Typing the response with generics (`apiClient.get<MyType>(...)`)

**Base URL:** Reads `VITE_API_BASE_URL` env var, falls back to `http://localhost:8000`. Set this in `.env` for staging/production.

**Do not:** manually fetch the auth token, set Authorization headers, or call `fetch()` for backend API endpoints. Use the client.

---

## Development Workflow

### Running Locally

**Backend:**

```bash
cd backend
uv run uvicorn app.main:app --reload
# Runs on http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Frontend:**

```bash
cd frontend
npm run dev
# Runs on http://localhost:5173
```

### Environment Variables

**Never commit `.env` files.** Use `.env.example` as templates.

**Backend `.env`:**

```bash
APP_ENV=development
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # Secret key, never expose to frontend
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ALLOWED_ORIGINS=["http://localhost:5173"]
```

**Frontend `.env`:**

```bash
PUBLIC_SUPABASE_URL=https://xxx.supabase.co
PUBLIC_SUPABASE_ANON_KEY=eyJ...  # Publishable key, safe for browser
```

The `PUBLIC_` prefix in SvelteKit means the var is exposed to the browser.

### Git Workflow

- Main branch is protected and auto-deploys to production
- Feature branches for new work
- Descriptive commit messages: `feat:`, `fix:`, `docs:`, `chore:`
- Push early and often

---

## Key Architectural Decisions

### Monorepo

- Frontend and backend in one repo for easier coordination
- Shared documentation (`DESIGN.md`, `CLAUDE.md`)
- Single source of truth

### Authentication Flow

- Supabase Auth handles all auth (email/password for V1, magic links in V2)
- Frontend uses `@supabase/supabase-js` client
- Backend uses service role key for admin operations
- Row Level Security enforces data isolation at DB level

### Data Flow: Frontend → Backend → Database

```
User Action (Frontend)
    ↓
Supabase Client (validates auth)
    ↓
FastAPI Endpoint (business logic)
    ↓
Supabase Service (via service role key)
    ↓
PostgreSQL (RLS enforces user isolation)
```

### LLM Integration Strategy

**Division of Labor:**

- **Python calculates statistics** (counts, frequencies, co-occurrences) - deterministic, exact
- **OpenAI generates narratives (Claude in production)** from those statistics - meaning-making, educational context
- **Never send raw symptom logs to the LLM** - send calculated patterns + cached summary only

**Anonymization:**

- Strip all PII before sending to the LLM (no names, emails, exact DOB)
- Use relative dates ("Day 1, Day 3, Day 7") not absolute dates
- Send only relevant symptom subsets, not full history
- Cached summary format: "Most frequent symptoms last 30 days: fatigue 18x, brain fog 12x"

**Prompt Architecture (4 layers):**

1. Core identity (who Meno is, what it does/doesn't do)
2. Source grounding (cite everything, use provided docs only)
3. Behavioral guardrails (soft redirects, no medical advice, current HRT evidence)
4. Dynamic context (user journey stage, age, cached summary, RAG chunks)

### LLM Provider Strategy (Development vs Production)

#### Current Approach: OpenAI for Development

**Why OpenAI for V1:**

- Free API tier during development (no training data usage)
- Cost-effective while building and iterating
- Functionally equivalent to Claude for our use cases
- Same embedding model (text-embedding-3-small) for RAG

**Models Used:**

- **Chat completions:** gpt-4o-mini (development) or gpt-4o (if needed)
- **Embeddings:** text-embedding-3-small (development and production)

#### Future Migration to Claude (Production)

**When to migrate:**

- App is ready for production/monetization
- Need Claude's superior reasoning for complex medical context
- Budget allows for Claude API costs

**Migration is straightforward** — the APIs are very similar:

```python
# OpenAI (current)
from openai import OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)
text = response.choices[0].message.content

# Claude (future)
from anthropic import Anthropic
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
text = response.content[0].text
```

**Key differences:**

- Response structure: `.choices[0].message.content` vs `.content[0].text`
- Claude requires `max_tokens` parameter (OpenAI has a default)
- Otherwise identical message format and behavior

**Abstraction strategy:**
Create a thin wrapper in `backend/app/services/llm.py` that provides a unified interface:

```python
def chat_completion(messages: list[dict], max_tokens: int = 1024) -> str:
    if settings.LLM_PROVIDER == "openai":
        # OpenAI logic
    elif settings.LLM_PROVIDER == "claude":
        # Claude logic
```

This way the migration is a single environment variable change + updating one wrapper file.

**Files that will need updates during migration:**

- `backend/app/services/llm.py` (wrapper implementation)
- `backend/app/core/config.py` (add `LLM_PROVIDER` setting)
- `.env` files (keep both API keys during transition)
- Tests (mock the wrapper, not the provider directly)

#### Why Claude for Production?

- **Better reasoning:** Claude excels at nuanced medical context and multi-step reasoning
- **Stronger guardrails:** Better at following complex system prompts (medical advice boundary)
- **Citation handling:** More reliable at maintaining inline citations throughout responses
- **Safety alignment:** Anthropic's focus on AI safety aligns with health data sensitivity

The design of Meno (Python calculates, LLM narrates) means the LLM provider is a swappable component, not a fundamental architecture decision.

### RAG Pipeline

**Knowledge Sources:**

- Menopause Wiki (menopausewiki.ca) - scraped with permission
- 75-150 curated PubMed papers (post-2015 emphasis, high-quality filters)
- The Menopause Society guidelines
- British Menopause Society guidelines

**Embedding Strategy:**

- Development: sentence-transformers (free, runs locally)
- Production: OpenAI text-embedding-3-small (1536 dimensions)
- Storage: pgvector in Supabase (vector similarity search)

**Chunking:**

- Wiki: 500 tokens per chunk, 50 token overlap, by section
- PubMed: abstract, methods, results, conclusion as separate chunks
- Metadata: source URL, title, publication date, section name, study type

**Retrieval:**

- Cosine similarity search via pgvector
- Top 5 chunks per query
- Hybrid search (semantic + keyword) in V2

---

## Privacy & Ethics Principles

### Data Ownership

- Users own their data
- Full export available anytime
- Account deactivation deletes all personal data (30-day soft delete, then hard delete)
- Data never sold or shared

### Medical Advice Boundary

**Acceptable:**

- "Research suggests sleep disruption is common during perimenopause"
- "Your logs show sleep and brain fog co-occurring frequently"
- "Here are questions to ask your provider about hormone therapy"

**Not Acceptable:**

- "You have perimenopause" (diagnosis)
- "You should take X supplement" (treatment recommendation)
- "You don't need to see a doctor" (replacing medical advice)

**Implementation:**

- System prompts enforce this boundary
- Soft redirects for out-of-scope questions
- Hard stop for prompt injection attempts
- Disclaimers throughout UI

### Security

- All secrets in `.env` files, never committed
- Row Level Security on all user data tables
- HTTPS only in production
- Supabase handles auth token security
- Backend validates all requests even though RLS provides defense-in-depth

---

## Current Development Phase

**V1 Status:** Database schema complete, auth working, UI shell built

**Next Priority: Backend API Development**

- Create FastAPI endpoints for symptom logging
- Connect frontend to backend
- Implement proper error handling and logging
- Add comprehensive tests

**Deferred to V2:**

- Period tracking
- Medication tracking
- MCP servers for RAG and provider search
- Magic link auth (using password auth in V1)
- Mobile app
- Map view for providers

---

## Working with Claude Code

### When to Use Context7 MCP

Always use Context7 for live documentation on:

- SvelteKit (fast-moving, lots of Svelte 5 changes)
- FastAPI patterns
- Supabase SDK
- Anthropic SDK (Claude API)
- Tailwind CSS
- shadcn-svelte components

### Request Patterns

**For new features:**

1. Reference this file (`CLAUDE.md`) and `DESIGN.md`
2. Specify which section you're implementing
3. Request tests alongside implementation
4. Ask for error handling and logging

**Example prompt:**

> "Using the context in CLAUDE.md and the database schema in DESIGN.md section 9, implement a FastAPI endpoint for creating symptom logs. Include:
>
> - Pydantic models for request/response
> - Proper error handling with HTTPException
> - Logging of key events
> - pytest tests with mocked Supabase calls
> - Validation that user can only create logs for themselves
>
> Use Context7 to reference FastAPI and Supabase documentation."

**For debugging:**

> "This endpoint is failing with [error]. Check against the patterns in CLAUDE.md and help me debug. Use Context7 for FastAPI error handling best practices."

### File Creation Guidelines

- Backend code goes in `backend/app/` following the structure in this doc
- Tests mirror source structure in `backend/tests/`
- Frontend components in `frontend/src/lib/components/`
- Routes in `frontend/src/routes/` (respect the `(auth)` and `(app)` groups)

---

## Testing Strategy

### Backend Testing (pytest)

**What to test:**

- API endpoints (happy path + error cases)
- Business logic in services
- Data validation in models
- RAG retrieval accuracy (V2)

**What NOT to test:**

- Supabase internals (mock it)
- PostgreSQL functions (trust the DB)
- Third-party APIs (mock them)

**Mock Strategy: Supabase Fluent API Mocking**

The Supabase client uses a fluent query API (`table().select().eq().execute()`) that's easy to mock incorrectly.
Naive mocking breaks when code adds/removes chain calls.

**Use `setup_supabase_response()` helper for chain-agnostic mocks:**

```python
from tests.fixtures.supabase import setup_supabase_response

@pytest.mark.asyncio
async def test_create_symptom_log(mock_supabase):
    """Test symptom log creation."""
    # Set up response data
    setup_supabase_response(
        mock_supabase,
        data=[{"id": "123", "symptoms": ["fatigue"]}]
    )

    # Query chain doesn't matter — mock handles any length/order
    repo = SymptomRepository(mock_supabase)
    result = await repo.create("user-123", {"symptoms": ["fatigue"]})

    assert result["id"] == "123"
```

**Why this works:**

The helper sets up all Supabase chainable methods to return the same mock chain object.
This allows unlimited chaining without breaking when code changes.

**Available helpers (in `tests/fixtures/supabase.py`):**

- `setup_supabase_response(mock, data=[], error=None)` — Success response
- `setup_supabase_error(mock, message)` — Error response
- `setup_supabase_not_found(mock)` — Empty result
- `@pytest.fixture mock_supabase` — Pre-configured fixture

See "Part 4: Testing Patterns" in `docs/dev/backend/V2CODE_EXAMPLES.md` for full examples.

### Frontend Testing (Vitest)

**Focus on:**

- Component logic (not visual regression)
- Form validation
- API call handling
- Auth state management

**V1:** Basic unit tests
**V2:** Consider Playwright for e2e tests

---

## Useful Commands Reference

```bash
# Backend
cd backend
uv add <package>              # Install dependency
uv add --dev <package>        # Install dev dependency
uv run pytest                 # Run tests
uv run pytest -v              # Verbose test output
uv run pytest --cov           # With coverage
uv run ruff check .           # Lint
uv run ruff format .          # Format
uv run uvicorn app.main:app --reload  # Run dev server

# Frontend
cd frontend
npm install <package>         # Install dependency
npm run dev                   # Run dev server
npm run build                 # Build for production
npm run preview               # Preview production build
npm test                      # Run tests

# Database (Supabase dashboard)
# SQL Editor for running migrations
# Authentication for managing users
# Table Editor for viewing data
```

---

## Resources

- **Design Document:** `docs/dev/DESIGN.md` - comprehensive spec
- **Supabase Dashboard:** https://supabase.com/dashboard
- **Anthropic Console:** https://console.anthropic.com
- **Menopause Wiki:** https://menopausewiki.ca
- **NAMS Directory:** https://www.menopause.org/for-women/find-a-menopause-practitioner

---

**Remember:** This is a living document. Update it as architectural decisions change or new patterns emerge. Future you (and future Claude Code sessions) will thank you.
