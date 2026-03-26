---
status: ready
priority: p3
issue_id: "082"
tags: [code-review, security, frontend, xss, pr-10]
dependencies: []
---

# {#html} in ask/+page.svelte uses marked without DOMPurify — XSS risk

## Problem Statement

`ask/+page.svelte` line 290 uses `{@html renderContent(message.content, message.citations)}` to render AI response markdown. The `renderContent` function pipes through `marked` then a custom `sanitizeMarkdownHtml` function. `marked`'s documentation explicitly states it does not sanitize output and recommends pairing with DOMPurify. The custom sanitizer may not cover all attack vectors.

This is pre-existing (not introduced by PR #10) but documented here for tracking.

## Findings

- `ask/+page.svelte` line 290: `{@html renderContent(message.content, message.citations)}`
- Content source: LLM API responses (Claude/OpenAI) — not direct user input, but LLM output can contain adversarial content via prompt injection
- The `sanitizeMarkdownHtml` function validates link protocols (http/https allowlist) and uses `escapeHtml` on citation URLs
- `marked` itself does not sanitize and recommends DOMPurify pairing
- Identified by security-sentinel

## Proposed Solutions

### Option 1: Add DOMPurify (Recommended)

```bash
npm install dompurify
npm install -D @types/dompurify
```

In `$lib/markdown.ts`, add after `marked` rendering:

```typescript
import DOMPurify from 'dompurify';

export function renderContent(content: string, citations: Citation[]): string {
  const rawHtml = renderMarkdown(content);
  const clean = DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: ['p', 'a', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'sup'],
    ALLOWED_ATTR: ['href', 'class', 'target', 'rel', 'data-citation-id']
  });
  return injectCitationLinks(clean, citations);
}
```

**Pros:** Defense-in-depth against XSS from LLM output
**Effort:** Small (1–2 hours including testing)
**Risk:** Low — additive change, DOMPurify is well-tested

## Recommended Action

Option 1. Important for a health app where AI output is rendered as HTML.

## Technical Details

- `frontend/src/routes/(app)/ask/+page.svelte` line 290
- `frontend/src/lib/markdown.ts` (likely location of `renderContent`)

## Acceptance Criteria

- [ ] `dompurify` is installed as a dependency
- [ ] All `{@html}` output is sanitized through DOMPurify before rendering
- [ ] Allowlist of tags and attributes is explicit and minimal
- [ ] Citation links survive the sanitization (test with real API response)

## Work Log

- 2026-03-25: Identified by security-sentinel in PR #10 review
