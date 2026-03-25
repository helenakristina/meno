---
status: complete
priority: p1
issue_id: "063"
tags: [code-review, security, hallucination, citations, health-safety]
dependencies: []
---

# No source overlap verification on primary structured path — hallucination undetected

## Problem Statement

In v1, `render_structured_response` ran `_claim_source_overlap` on every claim to verify the cited source actually supported the claim. In v2, this check was removed from the primary path. The new code trusts the LLM completely — `source_index` is used only to build the citation display, with no verification that the paragraph body is actually supported by the cited chunk.

This means the LLM can generate a paragraph containing health information from its training data, cite a topically adjacent but non-supporting source, and the system will present it to users with a credible citation. This is the primary hallucination risk for a health information app.

The overlap check still exists in `CitationService` but is only called in the fallback pipeline (triggered when JSON parsing fails), not on normal structured responses.

## Findings

- `backend/app/services/citations.py:render_structured_response` — no call to `_claim_source_overlap`
- `backend/app/services/ask_meno.py:307–320` — `verify_citations` called only in except/fallback block
- `_claim_source_overlap` method still present in `citations.py` (unused on primary path)
- For a health app, an unsupported claim attributed to Menopause Society or PubMed is a safety issue
- Confirmed by: architecture-strategist (P1), security-sentinel (P2)

## Proposed Solutions

### Option 1: Add section-level overlap logging in render_structured_response (Recommended)

**Approach:** After resolving the chunk, run `_claim_source_overlap(section.body, chunk_content)` and log a WARNING when score falls below `_RELEVANCE_MIN_OVERLAP`. Don't strip the section — a whole paragraph stripping would degrade voice quality — but make the mismatch visible for monitoring.

```python
chunk_content = chunk.get("content", "")
overlap = self._claim_source_overlap(body, chunk_content)
if overlap < self._RELEVANCE_MIN_OVERLAP:
    logger.warning(
        "render_structured_response: low overlap for section source_index=%d overlap=%.2f",
        idx,
        overlap,
    )
```

**Pros:** Restores observability. Doesn't degrade voice quality. Surfaces hallucinations in logs.
**Cons:** Still doesn't strip hallucinated content from user-facing output.
**Effort:** Small.

### Option 2: Strip section if overlap fails (More protective)

**Approach:** If overlap check fails and `insufficient_sources` is False, strip the section and log at WARNING.

**Pros:** No hallucinated content reaches users.
**Cons:** May strip legitimate content if the LLM paraphrases significantly. Could degrade response quality for low-overlap but factually correct paragraphs.
**Effort:** Small.

### Option 3: Add `overlap_score` to ResponseSection and validate post-parse

**Approach:** Run overlap check for all sections after `render_structured_response`, log a summary, and set a flag in `ChatResponse` for low-confidence responses.

**Pros:** Full observability, backward-compatible API addition.
**Cons:** More complex.
**Effort:** Medium.

## Recommended Action

Option 1 as a minimum to restore observability before launch. Consider Option 2 before production if the health safety risk outweighs voice quality concerns.

## Technical Details

- **Affected files:** `backend/app/services/citations.py`
- `_claim_source_overlap` and `_RELEVANCE_MIN_OVERLAP` are already present in `CitationService`

## Acceptance Criteria

- [ ] Primary structured path in `render_structured_response` checks source overlap for each section
- [ ] Low-overlap sections are logged at WARNING level
- [ ] Tests added for the overlap check on the structured path
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by architecture-strategist and security-sentinel in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
