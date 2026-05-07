# CLAUDE.md — Meno

Meno helps women navigate perimenopause and menopause with evidence-based information
and compassionate support. It is a health app handling sensitive medical data.

**What Meno is:** Symptom tracking, educational resource, LLM-powered pattern
recognition, provider discovery, bridge to informed healthcare conversations.

**Hard boundary:** Meno provides information and pattern recognition — never diagnosis
or treatment recommendations. This constraint is enforced at the prompt, UI, and
review levels. Do not cross it.

---

## Tech Stack

**Frontend:** SvelteKit 2.x, Svelte 5 (runes), TypeScript strict, Tailwind CSS 4.x,
shadcn-svelte, Supabase client (`@supabase/supabase-js`, `@supabase/ssr`), Node 25+

**Backend:** FastAPI (Python 3.11+), async/await throughout, uv for deps,
Supabase (PostgreSQL 15+ with pgvector), Anthropic API (Claude Sonnet 4),
OpenAI API (text-embedding-3-small, prod), sentence-transformers (local dev)

**Infrastructure:** Vercel (frontend), Railway (backend), Supabase (DB/auth/storage)

---

## Repository Structure

```
meno/
├── CLAUDE.md
├── docs/dev/
│   ├── DESIGN.md                        ← DB schema (Section 9), full architecture
│   └── backend/
│       ├── V2CODE_EXAMPLES.md           ← Backend pattern examples (non-authoritative)
│       ├── LOGGING.md                   ← PII-safe logging guide
│       └── VERTICAL_SLICE_EXAMPLE.md   ← Complete feature walkthrough
├── frontend/
│   └── src/
│       ├── lib/
│       │   ├── components/ui/           ← shadcn-svelte primitives
│       │   ├── api/client.ts            ← Typed API client (browser only)
│       │   ├── supabase/client.ts
│       │   ├── stores/                  ← Shared state (.ts files)
│       │   ├── types/                   ← Domain + API types, exported from index.ts
│       │   └── schemas/                 ← Zod schemas for forms
│       └── routes/
│           ├── (auth)/                  ← No nav: login, onboarding
│           ├── (app)/                   ← With nav: dashboard, log, ask, providers
│           └── practice/
└── backend/
    └── app/
        ├── main.py                      ← FastAPI entry + global exception handlers
        ├── core/                        ← config.py (pydantic-settings), supabase.py
        ├── api/
        │   ├── routes/                  ← HTTP endpoints (thin — call services only)
        │   └── dependencies.py          ← All DI wiring lives here
        ├── models/                      ← Pydantic models
        ├── repositories/                ← Supabase queries
        ├── services/                    ← Business logic + orchestration
        ├── utils/                       ← Pure functions, logging helpers
        ├── exceptions.py                ← Domain exception hierarchy
        └── rag/                         ← RAG pipeline
    └── tests/
        └── fixtures/supabase.py         ← Supabase mock helpers
```

---

## Backend Architecture

Layer order (strict — do not skip or invert):

```
Routes (thin)  →  Services (logic)  →  Repositories (data)
                       ↓
                  Providers (external APIs via ABC)
                       ↓
                  Utils (pure functions, no side effects)
```

Build order for any new feature: **Models → Repository → Service → Dependencies → Route → Tests**

All DI wiring goes in `dependencies.py` only. Routes never instantiate anything.

---

## LLM + RAG Strategy

**Division of labor:** Python calculates statistics (deterministic). LLM generates
narratives from those stats. Never send raw symptom logs to the LLM — send
calculated patterns + cached summary only.

**Anonymization:** Strip all PII before LLM calls. Use relative dates ("Day 1, Day 3").
Send only relevant symptom subsets.

**Prompt architecture (4 layers):**
Core identity → Source grounding → Behavioral guardrails → Dynamic context
(journey stage, age, cached summary, RAG chunks)

**LLM provider:** OpenAI gpt-4o-mini (dev) / Claude Sonnet 4 (prod).
Swappable via `LLM_PROVIDER` env var + thin wrapper in `app/services/llm.py`.

**RAG pipeline:**
- Sources: Menopause Wiki (with permission), curated PubMed papers (post-2015),
  Menopause Society + British Menopause Society guidelines
- Embeddings: sentence-transformers (dev) / text-embedding-3-small (prod, 1536 dims)
- Storage: pgvector in Supabase, cosine similarity, top 5 chunks per query
- Chunking: Wiki 500 tokens/50 overlap by section; PubMed by abstract/methods/results/conclusion

---

## Authentication

Supabase Auth, email/password (V1). Frontend uses `@supabase/supabase-js`.
Backend uses service role key. RLS enforces data isolation at DB level.

```
User Action → Supabase Client (auth) → FastAPI (logic) → Supabase Service (service key) → PostgreSQL (RLS)
```

---

## Database

Full schema in `docs/dev/DESIGN.md` Section 9.

Key tables: `users`, `symptom_logs`, `symptoms_reference`, `symptom_summary_cache`,
`conversations`, `providers`, `exports`, `rag_documents`

All user-data tables have RLS via `auth.uid()`. Reference tables (`symptoms_reference`,
`providers`) have no RLS.

---

## Commands

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload          # Dev server (localhost:8000)
uv run pytest -v -m "not integration"         # Unit tests
uv run pytest --cov -m "not integration"      # Unit tests + coverage
uv run ruff check . && uv run ruff format .   # Lint + format
uv add <package>                              # Add dependency
uv add --dev <package>                        # Add dev dep

# Frontend
cd frontend
npm run dev      # Dev server (localhost:5173)
npm run build    # Production build
npm test         # Tests
```

---

## Rules + Skills Index

Rules load automatically based on which files are being edited.
Skills are invoked on demand (by you or by /ce: commands).

**Global rules (always loaded):**
- `.claude/rules/medical-advice-boundary.md` — hard stops, never cross these
- `.claude/rules/pii-logging.md` — health data logging, non-negotiable
- `.claude/rules/tdd-core.md` — CATCHES comments, TDD cycle, mutation notes

**Path-scoped rules (auto-loaded on file match):**
- `.claude/rules/backend/routes.md` — `backend/app/api/routes/**/*.py`
- `.claude/rules/backend/services.md` — `backend/app/services/**/*.py`
- `.claude/rules/backend/repositories.md` — `backend/app/repositories/**/*.py`
- `.claude/rules/backend/providers.md` — `backend/app/providers/**/*.py`
- `.claude/rules/backend/dependencies.md` — `backend/app/api/dependencies.py`
- `.claude/rules/backend/utils.md` — `backend/app/utils/**/*.py`
- `.claude/rules/frontend/svelte-components.md` — `frontend/src/**/*.svelte`
- `.claude/rules/frontend/server-actions.md` — `frontend/src/**/+page.server.ts`, `+layout.server.ts`
- `.claude/rules/frontend/stores.md` — `frontend/src/lib/stores/**/*.ts`
- `.claude/rules/frontend/types-schemas.md` — `frontend/src/lib/{types,schemas}/**/*.ts`
- `.claude/rules/tests/backend.md` — `backend/tests/**/*.py`
- `.claude/rules/tests/frontend.md` — `frontend/src/**/*.test.ts`

**Skills:**
- `.claude/skills/scaffold-feature/` — end-to-end feature scaffolding (models → tests)
- `.claude/skills/add-provider/` — three-file ABC provider pattern
- `.claude/skills/scaffold-wizard-flow/` — multi-step wizard pattern (orchestrator + steps)
- `.claude/skills/ce-review/` — mutation audit, CATCHES check, self-confirmation check
- `.claude/skills/testing-discipline/` — CE workflow hooks (/ce:plan, /ce:work, /ce:review, /ce:compound)
- `.claude/skills/meno-design-system/` — design tokens and component patterns

---

## Compaction Instructions

When compacting, always preserve: the full list of modified files, test commands
that were run, the current feature being implemented, and any errors encountered.