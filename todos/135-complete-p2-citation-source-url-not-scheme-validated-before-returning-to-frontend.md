---
status: pending
priority: p2
issue_id: "135"
tags: [code-review, security, xss, citations, frontend]
---

# `Citation.url` not scheme-validated — `javascript:` URIs could reach the frontend

## Problem Statement

`backend/app/services/citations.py` lines 246–250 (`render_structured_response`) and lines 338–344 (`extract`) both build `Citation` objects directly from `chunk.get("source_url", "")` with no URL scheme validation:

```python
url = chunk.get("source_url", "")
# ...
if url:
    citations.append(Citation(url=url, title=title, ...))
```

If a RAG document row contained a `javascript:`, `data:`, or `vbscript:` URI, it would be serialised and returned to the frontend as a valid citation link. If the frontend renders `Citation.url` as `<a href>` without scheme-checking, this is an XSS precursor.

**Current frontend mitigation unknown** — the frontend citation rendering should be checked. But defence in depth requires the backend to validate URLs before returning them to clients.

## Proposed Solution

Validate the URL scheme at citation construction time. Drop any non-HTTP URL silently (empty string, so the citation is rendered without a link but still shows title):

```python
# In both render_structured_response (line ~246) and extract (line ~338)
url = chunk.get("source_url", "")
if not url.startswith(("https://", "http://")):
    url = ""
```

All legitimate RAG sources in this app (Menopause Wiki, PubMed, BMS/Menopause Society guidelines) have HTTPS URLs.

**Effort:** Small (2 locations in citations.py)  
**Risk:** None — any non-HTTP source_url is already invalid for this app's sources

## Acceptance Criteria

- [ ] `citations.py` `render_structured_response`: `javascript:`, `data:`, non-HTTP URLs result in `url=""` in Citation
- [ ] `citations.py` `extract`: same scheme validation applied
- [ ] Tests: `test_citations.py` includes a case where source_url is `javascript:alert(1)` and confirms it's stripped
- [ ] Valid `https://` URLs are unaffected

## Work Log

- 2026-04-21: Identified by PR #25 security review (security-sentinel). Defence-in-depth — frontend should also validate, but backend must not trust DB content.
