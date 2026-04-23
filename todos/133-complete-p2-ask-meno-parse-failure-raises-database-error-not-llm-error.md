---
status: pending
priority: p2
issue_id: "133"
tags: [code-review, python, error-handling, ask-meno, exceptions]
dependencies: ["128"]
---

# JSON parse failure at `ask_meno.py:305` raises `DatabaseError` — should be `LLMError`

## Problem Statement

`backend/app/services/ask_meno.py` lines 274–305: the block that runs `json.loads(response_text)` and `StructuredLLMResponse(**raw_response)` catches all failures and raises `DatabaseError`:

```python
except Exception as exc:
    ...
    raise DatabaseError("Failed to parse structured LLM response") from exc
```

`LLMError` was added in this PR and its docstring explicitly covers: _"LLM response cannot be parsed (malformed JSON, Pydantic validation failure)"_. The wrong exception type is used here.

**Note:** Todo #128 was marked complete after `LLMError` was added and used for the LLM _call_ failure at line 264. The parse failure at line 305 was not updated — this is the remaining gap.

**Current user impact is masked** by the route-level catch at `chat.py:73`, which catches `(DatabaseError, LLMError)` and returns the same "temporarily unavailable" message for both. Users see the correct message today. But:

1. Log monitoring will misattribute LLM format regressions as database failures
2. Semantically incorrect — confuses future operators and reviewers
3. The `LLMError` global handler (which has the correct message) is bypassed for parse failures

## Proposed Solution

Change `ask_meno.py` line 305:

```python
# Before:
raise DatabaseError("Failed to parse structured LLM response") from exc

# After:
raise LLMError("Failed to parse structured LLM response") from exc
```

**Effort:** Trivial (1 line)  
**Risk:** None — route catches both, user-facing response unchanged

## Acceptance Criteria

- [ ] `ask_meno.py:305` raises `LLMError`, not `DatabaseError`
- [ ] `test_ask_meno_service.py`: `test_malformed_json_from_llm_raises_exception` asserts `pytest.raises(LLMError, match="...")`
- [ ] `test_chat.py`: `test_chat_malformed_json_from_llm_returns_500` still passes (route behavior unchanged)

## Work Log

- 2026-04-21: Identified as incomplete resolution of #128. LLMError was added for LLM call failure but not for parse failure.
