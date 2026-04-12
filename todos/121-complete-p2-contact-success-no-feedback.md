---
status: complete
priority: p2
issue_id: "121"
tags: [code-review, ux, frontend, contact]
---

# Contact form redirects silently to `/` with no confirmation message

## Problem Statement

After submitting the contact form, Formspree redirects to `_next: "/"` — the landing page. The user sees no confirmation that their message was received. For a health app where users may be sending sensitive or emotionally significant messages, a silent redirect to the home page erodes trust.

**File:** `frontend/src/routes/contact/+page.svelte:41`

```html
<input type="hidden" name="_next" value="/" />
```

## Findings

- **File:** `frontend/src/routes/contact/+page.svelte:41`
- **Flagged by:** architecture-strategist, kieran-typescript-reviewer

## Proposed Solutions

### Option A: Create `/contact/success` page and redirect there (recommended)

Change `_next` to `/contact/success` and create a simple static page at `frontend/src/routes/contact/success/+page.svelte` with a confirmation message.

```html
<input type="hidden" name="_next" value="/contact/success" />
```

The success page can reuse `PublicPageShell` (todo #120) and show a brief "Message sent" confirmation with a link back to the home page.

**Pros:** Clear feedback, simple static page, no JS required  
**Cons:** One new file  
**Effort:** Small  
**Risk:** None

### Option B: Remove `_next` and use Formspree's default thank-you page

Remove the hidden input entirely. Formspree shows its own confirmation page when `_next` is absent. The user sees confirmation, then can navigate back manually.

**Pros:** Zero code, immediate fix  
**Cons:** User leaves the Meno domain; Formspree's default page is generic  
**Effort:** Trivial  
**Risk:** None

### Option C: JavaScript fetch with inline success state

Replace the HTML POST with a `fetch()` to Formspree's JSON endpoint and show an inline success message in the page without a redirect.

**Pros:** Best UX, no page reload  
**Cons:** Requires JS, more code, needs loading/error state handling  
**Effort:** Medium  
**Risk:** Low

## Acceptance Criteria

- [ ] After submitting the contact form, the user sees a clear confirmation that their message was received
- [ ] User is not silently redirected to an unrelated page

## Work Log

- 2026-04-11: Identified by PR #22 code review (architecture-strategist, typescript-reviewer)
