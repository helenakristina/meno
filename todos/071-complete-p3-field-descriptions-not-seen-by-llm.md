---
status: complete
priority: p3
issue_id: "071"
tags: [code-review, pydantic, models, simplicity]
dependencies: []
---

# `Field(description=...)` on ResponseSection not seen by the LLM

## Problem Statement

`ResponseSection.body` and `ResponseSection.source_index` have verbose `Field(description=...)` values that read as behavioral instructions ("Write in Meno's voice: warm, direct, evidence-informed, human"). But the LLM is given JSON mode (`response_format="json"`), not structured output mode with schema injection. The `Field(description=...)` text appears only in OpenAPI docs — it is never sent to the LLM.

This is misleading: it looks like the descriptions enforce behavior on the model, but they don't. The actual behavioral instructions are in LAYER_2_VOICE and LAYER_3_SOURCE_RULES in the system prompt.

## Findings

- `backend/app/models/chat.py:250–262` — verbose `Field(description=...)` on `body` and `source_index`
- The LLM schema is manually written as a string in `LAYER_3_SOURCE_RULES`, not derived from Pydantic's `model_json_schema()`
- Field descriptions are visible at `/docs` (OpenAPI) but not in the LLM's context
- Confirmed by: code-simplicity-reviewer

## Proposed Solutions

### Option 1: Simplify to plain defaults with inline comments

```python
class ResponseSection(BaseModel):
    """A paragraph drawn from exactly ONE source."""

    heading: str | None = None
    body: str  # Plain prose, no markdown. One source only (see LAYER_3_SOURCE_RULES).
    source_index: int | None = None  # 1-based index of the cited source; null for closing remarks
```

**Pros:** Removes misleading pseudo-behavioral descriptions. Simpler. The real enforcement is in the system prompt.
**Cons:** Slightly less OpenAPI documentation detail.
**Effort:** Trivial.

## Recommended Action

Option 1.

## Acceptance Criteria

- [ ] `Field(description=...)` removed from `body` and `source_index` on `ResponseSection`
- [ ] Replaced with concise inline comments noting where the real behavioral enforcement lives
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by code-simplicity-reviewer in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
2026-03-25: Resolved.
