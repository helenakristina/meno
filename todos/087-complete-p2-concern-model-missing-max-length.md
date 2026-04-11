---
status: pending
priority: p2
issue_id: "087"
tags: [code-review, security, backend, validation]
dependencies: []
---

# `Concern.text` and `Concern.comment` have no server-side `max_length`

## Problem Statement

The `Concern` Pydantic model has no length limits. The frontend enforces 200 chars for `comment` via `maxlength` HTML attribute, but there is no server-side enforcement. Arbitrarily long values are stored in JSONB and concatenated into LLM prompts, potentially blowing the 2000-char `sanitize_prompt_input` ceiling and silently truncating the user's actual concerns.

## Findings

- **File**: `backend/app/models/appointment.py`, lines 48–52
- `comment` limit documented as 200 chars in PRD but not enforced in model
- `text` has no limit at all
- Both fields are joined and passed into scenario and PDF LLM prompts: `f"{c.text}; {c.comment}"`
- `sanitize_prompt_input` truncates at 2000 chars total — without per-field limits, one large comment silently drops other concerns from the LLM context

## Proposed Solution

```python
class Concern(BaseModel):
    text: str = Field(
        description="The concern text",
        min_length=1,
        max_length=500,
    )
    comment: str | None = Field(
        default=None,
        description="Optional context for this concern",
        max_length=200,
    )
```

## Acceptance Criteria

- [ ] `Concern.text` has `min_length=1, max_length=500` (or similar agreed limit)
- [ ] `Concern.comment` has `max_length=200` matching frontend enforcement
- [ ] Test: `SaveConcernsRequest` with oversized `text` returns 422
- [ ] Test: `SaveConcernsRequest` with oversized `comment` returns 422
