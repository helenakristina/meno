---
status: complete
priority: p3
issue_id: "124"
tags: [code-review, security, frontend, privacy]
---

# Privacy policy names Supabase — unnecessary vendor disclosure

## Problem Statement

`frontend/src/routes/privacy/+page.svelte` line 45 states "Authentication is handled by Supabase." Naming the auth vendor in a public-facing privacy policy is unnecessary information disclosure. It tells an attacker which provider is in use, narrowing the attack surface to Supabase-specific CVEs and RLS misconfiguration patterns.

This is low-severity because Supabase is widely used and not a secret. But a production privacy policy should say "third-party identity provider" — same meaning to users, less operational surface.

## Proposed Solution

Replace:

```
Authentication is handled by Supabase.
```

With:

```
Authentication is handled by a third-party identity provider.
```

**Effort:** Trivial  
**Risk:** None

## Acceptance Criteria

- [ ] "Supabase" does not appear in the privacy policy text

## Work Log

- 2026-04-11: Identified by PR #22 code review (security-sentinel)
