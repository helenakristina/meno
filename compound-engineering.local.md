---
review_agents:
  - compound-engineering:review:kieran-python-reviewer
  - compound-engineering:review:kieran-typescript-reviewer
  - compound-engineering:review:security-sentinel
  - compound-engineering:review:performance-oracle
  - compound-engineering:review:architecture-strategist
  - compound-engineering:review:code-simplicity-reviewer
---

## Project Review Context

Meno is a FastAPI + SvelteKit health app for perimenopause/menopause navigation.

**Key conventions:**

- Backend: Routes → Services → Repositories (strict layering). No HTTPException in services/repos — use domain exceptions from app.exceptions. ABC pattern for service interfaces. Pydantic v2 models. PII-safe logging (never log health data, use hash_user_id()).
- Frontend: Svelte 5 runes ($state, $derived, $props, onMount). All API calls via apiClient (never raw fetch). Mobile-first, WCAG 2.1 AA.
- Test naming: test_X_when_Y_then_Z. Mock Supabase via fixtures/supabase.py helpers.
- Medical advice boundary: never diagnose, never recommend treatment. Postmenopausal bleeding alert is informational only.

**Reference docs:** docs/dev/backend/V2CODE_EXAMPLES.md, docs/dev/frontend/V2CODE_EXAMPLES.md
