---
status: complete
priority: p1
issue_id: "118"
tags: [code-review, security, frontend, contact]
---

# Personal email address hardcoded in public HTML source

## Problem Statement

`frontend/src/routes/contact/+page.svelte` line 40 emits a personal email address verbatim into the page's HTML:

```html
<input type="hidden" name="_replyto" value="helenalucia@fastmail.com" />
```

`type="hidden"` hides the field from the rendered UI but not from the HTML source. Spam harvesters and scrapers that specifically target form hidden fields will index it. For a health app, the operator's personal email being publicly scrapeable is a phishing and spam surface.

The `_replyto` field is not required by Formspree for routing. Formspree already uses the submitter's `email` field (present in the form) as the reply-to automatically. The Formspree dashboard also allows setting a fixed reply-to address server-side.

## Findings

- **File:** `frontend/src/routes/contact/+page.svelte:40`
- **Flagged by:** security-sentinel, kieran-typescript-reviewer, architecture-strategist, code-simplicity-reviewer (all four agents independently identified this)

## Proposed Solutions

### Option A: Remove the hidden input (recommended)

Delete line 40 entirely. Formspree uses the submitter's `email` field as reply-to by default. No configuration needed.

**Pros:** Zero risk, one-line fix, email never in source  
**Cons:** None  
**Effort:** Small  
**Risk:** None

### Option B: Configure reply-to in Formspree dashboard

Remove the hidden input and set the reply-to in Formspree's form settings page.

**Pros:** Same result, slightly more explicit  
**Cons:** Requires Formspree dashboard access  
**Effort:** Small  
**Risk:** None

## Acceptance Criteria

- [ ] `helenalucia@fastmail.com` does not appear anywhere in the built HTML output
- [ ] Contact form still submits successfully to Formspree
- [ ] Formspree still routes replies correctly

## Work Log

- 2026-04-11: Identified by PR #22 code review (security-sentinel, typescript-reviewer, architecture-strategist, simplicity-reviewer)
