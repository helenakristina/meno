# CLAUDE.md - Development Context for Meno

**⚠️ DEV-ONLY POC** — Not deployed to production. See PRODUCTION_CHECKLIST.md for launch path.

- ✅ Medical advice boundary tested (GUARDRAILS_AUDIT.md)
- ⏳ Legal review (LEGAL_PREP.md — awaiting attorney)
- ⏳ Job + API cost plan (6 months)
- ⏳ Production deployment checklist

**Last Updated:** February 2026 | **Status:** Active Development - V1 Phase

---

## Project Overview

**Meno** helps women navigate perimenopause and menopause with evidence-based information and compassionate support.

**Core Mission:** Your symptoms are real. You don't have to just live with it. Help is available.

**What Meno Is:** Symptom tracking, educational resource, LLM-powered pattern recognition, provider discovery, bridge to informed healthcare conversations.

**What Meno Is NOT:** Not a diagnostic tool. Not a treatment recommendation engine. Not a replacement for medical advice. Not a medication management system (V1).

**Key Constraint:** We NEVER cross the line into medical advice. We provide information and pattern recognition, not diagnosis or treatment recommendations.

---

## Tech Stack

**Frontend:** SvelteKit 2.x, Svelte 5 (runes), TypeScript, Tailwind CSS 4.x, shadcn-svelte, Supabase client (`@supabase/supabase-js`, `@supabase/ssr`), Node 25+

**Backend:** FastAPI (Python 3.11+) async/await throughout, uv for deps, Supabase (PostgreSQL 15+ with pgvector), Anthropic API (Claude Sonnet 4), OpenAI API (text-embedding-3-small) for production embeddings, sentence-transformers for local dev embeddings

**Infrastructure:** Vercel (frontend), Railway (backend), Supabase (DB/auth/storage), GitHub

---

## Repository Structure

```
meno/
├── CLAUDE.md              ← You are here
├── docs/dev/
│   ├── DESIGN.md          ← Comprehensive design spec (DB schema in Section 9)
│   └── backend/
│       ├── V2CODE_EXAMPLES.md  ← Full backend patterns & examples
│       ├── LOGGING.md           ← PII-safe logging guide
│       └── VERTICAL_SLICE_EXAMPLE.md  ← Complete feature walkthrough
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/ui/  ← shadcn-svelte components
│   │   │   ├── api/client.ts   ← Backend API client (ALWAYS use this, never raw fetch)
│   │   │   ├── supabase/client.ts
│   │   │   └── stores/auth.ts
│   │   └── routes/
│   │       ├── (auth)/         ← No navigation (login, onboarding)
│   │       ├── (app)/          ← With navigation (dashboard, log, ask, providers, export)
│   │       └── practice/       ← Practice/learning pages
│   └── .env                    ← Never commit
└── backend/
    ├── app/
    │   ├── main.py             ← FastAPI entry + global exception handlers
    │   ├── core/               ← config.py (pydantic-settings), supabase.py
    │   ├── api/
    │   │   ├── routes/         ← HTTP endpoints (thin — just call services)
    │   │   └── dependencies.py ← FastAPI DI wiring
    │   ├── models/             ← Pydantic models (request/response/domain)
    │   ├── repositories/       ← Data access layer (Supabase queries)
    │   ├── services/           ← Business logic & orchestration
    │   ├── utils/              ← Shared business logic (dates, stats, logging)
    │   ├── exceptions.py       ← Domain exception hierarchy
    │   └── rag/                ← RAG pipeline
    ├── tests/                  ← Mirrors app/ structure
    │   └── fixtures/supabase.py ← Mock helpers
    ├── pyproject.toml
    └── .env                    ← Never commit
```

---

## Database Schema

Full schema in `docs/dev/DESIGN.md` Section 9.

**Key tables:** `users`, `symptom_logs`, `symptoms_reference` (34 symptoms, public), `symptom_summary_cache`, `conversations` (JSONB), `providers` (public), `exports` (immutable audit trail), `rag_documents` (vector embeddings)

**Security:** All user-data tables have RLS enabled via `auth.uid()`. Reference tables (`symptoms_reference`, `providers`) have no RLS.

---

## Backend Architecture

**All backend patterns and rules are in `.claude/skills/backend-development/SKILL.md`.** Consult it before writing any backend code.

Layer order: Routes (thin) → Services (logic) → Repositories (data) → Utils (pure functions).
Build order: Models → Repositories → Services → Dependencies → Routes → Tests.

Logging: `ruff` style. Google-style docstrings only when they add info the code doesn't convey. Type hints on all function signatures.

### PII-Safe Logging (CRITICAL)

**Health app logs must NEVER contain personal or medical data.** This includes symptom descriptions, user-generated text, health info, DOB, or plaintext user IDs.

- Log structure and metadata, never content
- Use `app.utils.logging`: `hash_user_id()`, `safe_len()`, `safe_keys()`, `safe_summary()`
- Full guide: `docs/dev/backend/LOGGING.md`

---

## Frontend

**All frontend patterns and rules are in `.claude/skills/frontend-development/SKILL.md`.** Consult it before writing any frontend code.

SvelteKit 2.x + Svelte 5 runes + TypeScript strict. Mobile-first (375px → 768px → 1024px). WCAG 2.1 Level AA. Tailwind utility classes.

**Svelte 5 Conventions (breaking changes from Svelte 4):** Use `$props()` not `export let`. Use `onclick={}` not `on:click={}`. Use `{@render children()}` not `<slot />`. Import from `$app/state` not `$app/stores`.

---

## Testing

**Testing philosophy and rules are in `.claude/skills/testing-discipline/SKILL.md`.** Consult it before writing any tests.

**Backend:** pytest + pytest-asyncio. Test files mirror source structure. Use `tests/fixtures/supabase.py` helpers for Supabase mocking.

**Frontend:** Vitest + @testing-library/svelte for components. Playwright for E2E (V2).

---

## LLM & RAG Strategy

**Division of labor:** Python calculates statistics (deterministic). LLM generates narratives from those stats (meaning-making). Never send raw symptom logs to the LLM — send calculated patterns + cached summary only.

**Anonymization:** Strip all PII before LLM calls. Use relative dates ("Day 1, Day 3"). Send only relevant symptom subsets.

**Prompt architecture (4 layers):** Core identity → Source grounding → Behavioral guardrails → Dynamic context (journey stage, age, cached summary, RAG chunks)

**LLM provider:** OpenAI (gpt-4o-mini) for development. Claude for production. Swappable via `LLM_PROVIDER` env var + thin wrapper in `app/services/llm.py`.

**RAG pipeline:**

- Sources: Menopause Wiki (with permission), 75-150 curated PubMed papers (post-2015), Menopause Society + British Menopause Society guidelines
- Embeddings: sentence-transformers (dev) / text-embedding-3-small (prod, 1536 dims)
- Storage: pgvector in Supabase, cosine similarity, top 5 chunks per query
- Chunking: Wiki 500 tokens/50 overlap by section; PubMed by abstract/methods/results/conclusion
- Hybrid search (semantic + keyword) in V2

---

## Privacy & Ethics

**Data ownership:** Users own their data. Full export anytime. Account deletion = 30-day soft delete then hard delete. Data never sold or shared.

**Medical advice boundary:**

- ✅ "Research suggests sleep disruption is common during perimenopause"
- ✅ "Your logs show sleep and brain fog co-occurring frequently"
- ✅ "Here are questions to ask your provider about hormone therapy"
- ❌ "You have perimenopause" (diagnosis)
- ❌ "You should take X supplement" (treatment recommendation)
- ❌ "You don't need to see a doctor" (replacing medical advice)

Enforced via system prompts, soft redirects, hard stops for prompt injection, UI disclaimers.

**Security:** Secrets in `.env` only (never committed). RLS on all user tables. HTTPS in production. Backend validates all requests (defense-in-depth with RLS).

---

## Authentication Flow

Supabase Auth: email/password for V1, magic links in V2. Frontend uses `@supabase/supabase-js`. Backend uses service role key. RLS enforces data isolation at DB level.

**Data flow:** User Action → Supabase Client (auth) → FastAPI Endpoint (logic) → Supabase Service (service key) → PostgreSQL (RLS)

---

## Current Phase

**V2 Status:** Appointment prep flow complete. Period tracking complete. Medication tracking in progress.

**Next priorities:** Ensure code meets standards. Increase tests in frontend.

**Deferred to V3:** MCP servers (RAG + provider search), magic link auth, mobile app, map view for providers.

---

## Commands Reference

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload     # Dev server (localhost:8000, docs at /docs)
uv run pytest -v -m "not integration"     # Unit Tests Only
uv run pytest --cov -m "not integration"  # Unit Tests with coverage
uv run ruff check . && uv run ruff format . # Lint + format
uv add <package>                          # Add dependency
uv add --dev <package>                    # Add dev dependency

# Frontend
cd frontend
npm run dev          # Dev server (localhost:5173)
npm run build        # Production build
npm test             # Tests
```

---

## Reference Documents

**Skills (authoritative rules — consult before writing code):**

- **Backend development:** `.claude/skills/backend-development/SKILL.md`
- **Frontend development:** `.claude/skills/frontend-development/SKILL.md`
- **Testing discipline:** `.claude/skills/testing-discipline/SKILL.md`

**Design & architecture:**

- **Design spec (DB schema, full architecture):** `docs/dev/DESIGN.md`

**Supplementary code examples (detailed reference, not authoritative — skills take precedence):**

- **Backend patterns & examples:** `docs/dev/backend/V2CODE_EXAMPLES.md`
- **Frontend patterns & examples:** `docs/dev/frontend/V2CODE_EXAMPLES.md`

**Operations:**

- **Supabase Dashboard:** https://supabase.com/dashboard
- **Anthropic Console:** https://console.anthropic.com

---

## Compaction Instructions

When compacting, always preserve: the full list of modified files, any test commands that were run, the current feature being implemented, and any errors encountered.

Always consult the skills in .claude/skills/ before writing code.
