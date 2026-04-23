---
status: complete
priority: p2
issue_id: "129"
tags: [code-review, security, logging, ask-meno]
---

# Raw `exc` embedded in `DatabaseError` messages — internal disclosure risk

## Problem Statement

`backend/app/services/ask_meno.py` lines 122, 133, 329, 412 embed the raw exception string in `DatabaseError` messages:

```python
raise DatabaseError(f"Failed to process question: {exc}") from exc
raise DatabaseError(f"Failed to save conversation: {exc}") from exc
raise DatabaseError(f"Failed to generate prompts: {str(exc)}") from exc
```

Supabase/asyncpg error strings can include table names, column names, constraint names, and query fragments. These are:

1. Forwarded to the route handler's `logger.error` call (with `exc_info=True`), so they appear in log aggregators — potentially exposing schema details to a log viewer
2. Stored in the `DatabaseError.message` field; if any future code path forwards that message to a client, it silently starts leaking Supabase internals

Contrast with the safe pattern already used on lines 264 and 305:

```python
raise DatabaseError("LLM call failed") from exc
raise DatabaseError("Failed to parse structured LLM response") from exc
```

Those use fixed strings. The original exception is still available via `from exc` and the `exc_info=True` log — no debugging information is lost.

## Proposed Solution

Replace all three dynamic messages with fixed strings:

```python
raise DatabaseError("Failed to fetch user context") from exc
raise DatabaseError("Failed to fetch symptom summary") from exc
raise DatabaseError("Failed to save conversation") from exc
raise DatabaseError("Failed to generate prompts") from exc
```

**Effort:** Trivial  
**Risk:** None — debugging info is preserved in the `from exc` chain and `exc_info=True` logs

## Acceptance Criteria

- [ ] No `f"...{exc}"` or `f"...{str(exc)}"` in `DatabaseError` raise statements in `ask_meno.py`
- [ ] Fixed strings used throughout, matching the pattern on lines 264 and 305

## Work Log

- 2026-04-15: Identified by PR #25 code review (security-sentinel)
