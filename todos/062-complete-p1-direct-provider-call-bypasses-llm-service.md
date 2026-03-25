---
status: complete
priority: p1
issue_id: "062"
tags: [code-review, architecture, ask-meno, llm]
dependencies: []
---

# `ask_meno.py` calls `.provider.chat_completion()` directly, bypassing LLMService

## Problem Statement

`AskMenoService.ask()` calls `self.llm_service.provider.chat_completion(...)` directly, bypassing `LLMService.chat_completion()`. This skips all validation, retry logic, and any future middleware added to `LLMService`. The `max_tokens=2000` and `temperature=0.5` are also set here directly — any future LLM guard (rate limiting, token caps, provider switching) added to `LLMService` will silently not apply to Ask Meno calls.

## Findings

- `backend/app/services/ask_meno.py:248` — `await self.llm_service.provider.chat_completion(...)`
- `LLMService.chat_completion()` exists and has validation (1–4096 token range, etc.)
- The `response_format="json"` parameter may not be supported by `LLMService.chat_completion()` — this may be why `.provider` is called directly
- Comment on line 246 says "lower temperature for source faithfulness" but temperature is now 0.5 (stale)
- Confirmed by: python-reviewer

## Proposed Solutions

### Option 1: Thread `response_format` through LLMService (Recommended)

**Approach:** Add `response_format: str | None = None` parameter to `LLMService.chat_completion()` and update the call in `ask_meno.py` to use the service layer.

```python
response_text = await self.llm_service.chat_completion(
    system_prompt=system_prompt,
    user_prompt=message,
    response_format="json",
    temperature=0.5,
    max_tokens=2000,
)
```

**Pros:** All future guards apply. Single layer of LLM access. Consistent with project patterns.
**Cons:** Requires updating LLMService and its tests.
**Effort:** Small.

### Option 2: Document the exception with a comment

**Approach:** Add a comment explaining why `.provider` is called directly.

**Pros:** Zero change.
**Cons:** Doesn't fix the architectural gap.
**Effort:** Trivial.
**Risk:** Misleading — implies the pattern is acceptable.

## Recommended Action

Option 1: add `response_format` to `LLMService.chat_completion()`.

## Acceptance Criteria

- [ ] `ask_meno.py` does not call `self.llm_service.provider.chat_completion()` directly
- [ ] `LLMService.chat_completion()` accepts `response_format` parameter
- [ ] Stale comment on line 246 updated
- [ ] Tests pass

## Work Log

- 2026-03-23: Found by python-reviewer in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
