---
status: done
priority: p1
issue_id: "075"
tags: [code-review, frontend, api-client, pr-10]
dependencies: []
---

# onboarding/+page.svelte uses raw fetch with hardcoded localhost:8000

## Problem Statement

`frontend/src/routes/(auth)/onboarding/+page.svelte` uses `fetch()` directly with a hardcoded `http://localhost:8000` base URL instead of `apiClient`. CLAUDE.md is explicit: "Always use `apiClient`, never raw fetch." This hardcoded URL silently fails on any environment other than local dev (staging, production, preview deployments). The onboarding flow is the first thing a new user hits — a failure here means no users can complete signup in non-local environments.

This file was touched in PR #10 (design token migration), making this the right moment to fix the pre-existing violation.

## Findings

- `frontend/src/routes/(auth)/onboarding/+page.svelte` line 7: `const API_BASE = 'http://localhost:8000';`
- Line 129: `const response = await fetch(\`${API_BASE}/api/users/onboarding\`, { ... })`
- The typed API endpoint `/api/users/onboarding` exists in `$lib/types/api.ts` — `apiClient.post` can be used directly
- Identified by kieran-typescript-reviewer

## Proposed Solutions

### Option 1: Replace with apiClient (Recommended)

Remove `API_BASE` constant and the raw `fetch` call. Replace with:

```typescript
const data = await apiClient.post('/api/users/onboarding', {
  journey_stage: formData.journey_stage,
  date_of_birth: formData.date_of_birth,
  // ... other fields
});
```

The `apiClient` reads `PUBLIC_API_URL` from env, handles auth headers, and works in all environments.

**Pros:** Consistent with every other API call in the codebase, works in all envs
**Effort:** Small (15 min)
**Risk:** Low — same HTTP call, different wrapper

## Recommended Action

Option 1. Fix before merge.

## Technical Details

- File: `frontend/src/routes/(auth)/onboarding/+page.svelte` lines 7 and ~129
- `apiClient` is already imported or can be added: `import { apiClient } from '$lib/api/client'`

## Acceptance Criteria

- [ ] No `fetch(` call in onboarding/+page.svelte
- [ ] No `localhost` string in any frontend source file (except .env.example comments)
- [ ] `API_BASE` constant removed
- [ ] Onboarding form submission uses `apiClient.post`

## Work Log

- 2026-03-25: Identified by kieran-typescript-reviewer in PR #10 review
2026-03-25: Resolved.
