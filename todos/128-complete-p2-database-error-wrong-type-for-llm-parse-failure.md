---
status: complete
priority: p2
issue_id: "128"
tags: [code-review, python, error-handling, ask-meno]
---

# `DatabaseError` is semantically wrong for LLM JSON parse failures

## Problem Statement

`backend/app/services/ask_meno.py` lines 297–305 wraps JSON parse and Pydantic validation failures in `DatabaseError`:

```python
except Exception as exc:
    logger.error("Structured response parse failed for user=%s (%s: %s)", ...)
    raise DatabaseError("Failed to parse structured LLM response") from exc
```

`DatabaseError` is defined as "Database operation failed (connection, query error, constraint violation)." A `json.JSONDecodeError` or Pydantic `ValidationError` from `StructuredLLMResponse(**raw_response)` is an **LLM response parsing failure** — nothing database-related failed.

**Two consequences:**

1. **Misleading operator signal.** Oncall sees a spike in `DatabaseError` → investigates DB/Supabase → finds nothing wrong. The actual cause (LLM returning malformed JSON) is hidden.

2. **Agent-observable behavior change.** Before this PR, a parse failure triggered the fallback pipeline and returned HTTP 200. Now it returns HTTP 500 with `{"detail": "Database error occurred"}`. Agents calling `/chat` that retry on 500 will retry on an LLM format regression, not a transient DB outage — they are different failure modes with different retry semantics.

The LLM call failure at line 264 has the same problem (`DatabaseError("LLM call failed")`) but that was pre-existing.

## Proposed Solution

**Option A — Add `LLMError` to exception hierarchy:**

```python
# app/exceptions.py
class LLMError(AppError):
    """LLM call or response parsing failure."""
```

Use `raise LLMError("Failed to parse structured LLM response") from exc` and map it to 502/503 in the global handler (upstream service failure, not our DB).

**Option B — Use existing `ValidationError`:**

`ValidationError` maps semantically closer (malformed data from upstream) and already exists. Map it to 422 or 502 in the global handler.

**Option C — Keep `DatabaseError` with a TODO comment:**

Minimal change: add a comment acknowledging the mismatch and flag for a future exception hierarchy cleanup. Acceptable if a new exception type is out of scope.

Option A is the right long-term fix. Option C is acceptable short-term if this PR is already large.

**Effort:** Small (Option A) or Trivial (Option C)  
**Risk:** Low — only changes exception type, not observable HTTP status if mapped to 500 in handler

## Acceptance Criteria

- [ ] Parse failures raise a semantically correct exception (not `DatabaseError`)
- [ ] OR a TODO comment documents the mismatch and links this issue
- [ ] Test at `test_ask_meno_service.py:563` updated to assert on specific exception type

## Work Log

- 2026-04-15: Identified by PR #25 code review (kieran-python-reviewer, agent-native-reviewer)
