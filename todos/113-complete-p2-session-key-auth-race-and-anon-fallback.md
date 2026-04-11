---
status: complete
priority: p2
issue_id: "113"
tags: [code-review, frontend, appointment-prep, security, auth, sessionstorage, svelte5]
---

# SESSION_KEY derived value has auth-race risk and writes health data under 'anon' fallback

## Problem Statement

`SESSION_KEY = $derived(\`appointmentPrepState_${$authState.user?.id ?? 'anon'}\`)` has two issues:

**1. Auth hydration race:** If `$authState.user` is null at component mount time (auth not yet resolved from SSR/client handshake), `SESSION_KEY` evaluates to `appointmentPrepState_anon`. The `onMount` sessionStorage read uses this 'anon' key — so the user-scoped saved state is never found and the wizard starts from scratch. More seriously, any `saveToSession()` call before auth resolves writes medical data under the shared 'anon' key.

**2. Over-reactive derived:** `SESSION_KEY` is a `$derived` that recomputes whenever `$authState` changes, but all consumers (`onMount`, `saveToSession`, `startOver`) run in non-reactive contexts. The reactivity is wasted complexity. A plain `let` set synchronously in `onMount` (after verifying user is non-null) is simpler and communicates the intent correctly.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` line 44
- **Current:**
  ```ts
  const SESSION_KEY = $derived(`appointmentPrepState_${$authState.user?.id ?? 'anon'}`);
  // ... used in onMount, saveToSession, startOver
  ```
- **Risk:** Writing medical data (narrative, clotting risk, breast cancer history) under 'anon' on a shared device means the next unauthenticated page load can access it before the logout clearance fires.

## Proposed Solutions

### Option A: Set key in onMount with null guard (Recommended)
```ts
let SESSION_KEY = '';
onMount(() => {
    const userId = get(authState).user?.id;
    if (!userId) return; // auth not resolved — don't restore (will re-resolve)
    SESSION_KEY = `appointmentPrepState_${userId}`;
    const saved = sessionStorage.getItem(SESSION_KEY);
    // ... restore logic
});
```
Requires importing `get` from `svelte/store`. Guarantees key is only set when user is known.

### Option B: Keep $derived but refuse to save when key contains 'anon'
```ts
function saveToSession() {
    if (SESSION_KEY.includes('anon')) return; // auth not resolved
    // ...
}
```
- Effort: XS | Risk: Low — simpler but doesn't fix the restore race

## Acceptance Criteria
- [ ] Medical data is never written to sessionStorage under a key containing 'anon'
- [ ] Session restore only runs when the user ID is known
- [ ] If auth is not yet resolved at mount time, the wizard starts fresh (not corrupted)

## Work Log
- 2026-04-11: Found during TypeScript, security, and performance reviews of commit e690800
