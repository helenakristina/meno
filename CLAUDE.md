# CLAUDE.md - Development Context for Meno

**Last Updated:** February 2026  
**Project Status:** Active Development - V1 Phase

---

## Project Overview

**Meno** is a web application that helps women navigate perimenopause and menopause with clarity, evidence-based information, and compassionate support.

**Core Mission:** You are not crazy. You don't have to just live with it. Help is available.

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

**Error Handling:**
- Use FastAPI's `HTTPException` for API errors
- Let exceptions bubble to FastAPI's exception handlers
- Log errors with context using Python's `logging` module
- Return proper HTTP status codes (400 for validation, 404 for not found, 500 for server errors)

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

**Key Patterns:**
```python
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

async def some_endpoint():
    try:
        # Business logic here
        logger.info("User action completed", extra={"user_id": user_id})
        return {"status": "success"}
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
```

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
let error = $state('');

async function handleSubmit() {
    loading = true;
    error = '';
    
    try {
        const { data, error: apiError } = await supabase
            .from('table')
            .select();
        
        if (apiError) throw apiError;
        
        // Success path
    } catch (e) {
        error = e.message;
        console.error('Operation failed:', e);
    } finally {
        loading = false;
    }
}
```

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
- **Claude generates narratives** from those statistics - meaning-making, educational context
- **Never send raw symptom logs to Claude** - send calculated patterns + cached summary only

**Anonymization:**
- Strip all PII before sending to Claude (no names, emails, exact DOB)
- Use relative dates ("Day 1, Day 3, Day 7") not absolute dates
- Send only relevant symptom subsets, not full history
- Cached summary format: "Most frequent symptoms last 30 days: fatigue 18x, brain fog 12x"

**Prompt Architecture (4 layers):**
1. Core identity (who Meno is, what it does/doesn't do)
2. Source grounding (cite everything, use provided docs only)
3. Behavioral guardrails (soft redirects, no medical advice, current HRT evidence)
4. Dynamic context (user journey stage, age, cached summary, RAG chunks)

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

**Mock Strategy:**
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_symptom_log():
    mock_supabase = AsyncMock()
    mock_supabase.from_().insert().execute.return_value = {
        "data": [{"id": "123", "symptoms": ["fatigue"]}],
        "error": None
    }
    
    with patch('app.core.supabase.supabase', mock_supabase):
        response = await create_symptom_log(...)
        assert response.status_code == 201
```

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
