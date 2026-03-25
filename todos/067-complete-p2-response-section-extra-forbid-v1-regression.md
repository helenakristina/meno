---
status: complete
priority: p2
issue_id: "067"
tags: [code-review, pydantic, models, schema-evolution]
dependencies: []
---

# `ResponseSection` needs `extra="forbid"` — v1 regression test relies on incidental behavior

## Problem Statement

`ResponseSection` has no `model_config` with `extra="forbid"`. The v1 regression test (`test_v1_json_format_triggers_fallback`) works correctly, but only because Pydantic raises a `ValidationError` when `body` is missing — not because extra fields (`claims`, `source_indices`) are explicitly rejected. If a future developer adds `body: str = ""` as a default, the v1 format would silently parse as valid, producing empty-body sections with no fallback.

Adding `extra="forbid"` makes schema evolution explicit and regression-safe.

## Findings

- `backend/app/models/chat.py:ResponseSection` — no `model_config`
- `backend/tests/services/test_ask_meno_service.py:test_v1_json_format_triggers_fallback` — passes by accident of missing-required-field error
- Confirmed by: architecture-strategist

## Proposed Solutions

### Option 1: Add `model_config = ConfigDict(extra="forbid")` to ResponseSection

```python
from pydantic import BaseModel, ConfigDict, Field

class ResponseSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str | None = None
    body: str = Field(...)
    source_index: int | None = Field(default=None, ...)
```

**Pros:** v1 payloads with extra fields fail explicitly. Schema evolution is safe. Regression test works by design.
**Cons:** None.
**Effort:** Trivial.

## Recommended Action

Add `ConfigDict(extra="forbid")`.

## Acceptance Criteria

- [ ] `ResponseSection` has `model_config = ConfigDict(extra="forbid")`
- [ ] v1 regression test still passes (and now works by design, not by accident)
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by architecture-strategist in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
