---
title: "LLMError vs DatabaseError: correct exception taxonomy for LLM parse failures"
category: architecture-issues
date: 2026-04-22
tags: [exceptions, llm, error-handling, ask-meno, exception-taxonomy]
related:
  - logic-errors/backend-phase4-type-safety-and-interface-cleanup.md
---

# LLMError vs DatabaseError for LLM Response Parse Failures

## Problem

After `LLMError` was added to the exception hierarchy (covering "LLM API call fails" and "LLM response cannot be parsed"), the JSON parse + Pydantic validation block in `ask_meno.py` still raised `DatabaseError`:

```python
except Exception as exc:
    raise DatabaseError("Failed to parse structured LLM response") from exc
```

This was semantically wrong: a `json.JSONDecodeError` or Pydantic `ValidationError` from `StructuredLLMResponse(**raw_response)` is entirely an LLM output failure. No database is involved. The mismatch caused:

1. **Misleading operator signal** — oncall sees a `DatabaseError` spike and investigates Supabase/DB, finding nothing wrong. The actual cause (LLM returning malformed JSON) is hidden.
2. **Wrong HTTP message** — `DatabaseError` handler returns `"Database error occurred"` to the user instead of `"The AI assistant is temporarily unavailable..."`.

The issue was partially masked because the route-level handler caught both `(DatabaseError, LLMError)` and returned the same user-facing message. But monitoring and log-based alerting would still misattribute the failure.

## Root Cause

`LLMError` was added and used for the LLM _call_ failure (line ~264 in `ask_meno.py`) but the nearby parse failure block (line ~305) was not updated. The two blocks look similar — both are LLM-related failures — but only one was updated.

## Fix

```python
# ask_meno.py — before:
raise DatabaseError("Failed to parse structured LLM response") from exc

# after:
raise LLMError("Failed to parse structured LLM response") from exc
```

## Rule: Match Exception Type to Root Cause, Not HTTP Status

When choosing which exception to raise, match the _cause_ of the failure, not its HTTP mapping:

| Failure cause                          | Exception             | HTTP |
| -------------------------------------- | --------------------- | ---- |
| DB connection, query, constraint       | `DatabaseError`       | 500  |
| LLM API call timeout/quota             | `LLMError`            | 500  |
| LLM returned malformed JSON            | `LLMError`            | 500  |
| LLM response fails Pydantic validation | `LLMError`            | 500  |
| Resource doesn't exist or wrong owner  | `EntityNotFoundError` | 404  |

`DatabaseError` and `LLMError` both map to HTTP 500, but they are different failure modes with different remediation and monitoring signals. Don't conflate them just because they share a status code.

## Docstring as Contract

`LLMError`'s docstring explicitly enumerates its valid causes:

```python
class LLMError(MenoBaseError):
    """LLM call or response parsing failure.

    Raised when:
    - LLM API call fails (timeout, quota, network error)
    - LLM response cannot be parsed (malformed JSON, Pydantic validation failure)
    ...
    """
```

When adding a new exception type, treat its `Raised when:` list as a contract. If a raise site fits that list, use that exception.

## Prevention

When adding `except` blocks that wrap external service calls (LLM, embeddings, storage):

- Check whether the exception type matches the failure domain
- If a new exception type was recently added to `exceptions.py`, grep for all related `except` blocks and verify they use the new type
- Test assertions should use the specific exception type: `pytest.raises(LLMError, match="...")` not `pytest.raises(Exception)`
