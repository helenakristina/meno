---
name: Deduplicate LLM Structured Content Methods
status: complete
priority: p3
tags: [code-review, refactor, code-quality]
dependencies: []
---

## Problem Statement

`generate_provider_summary_content` and `generate_cheatsheet_content` in `llm.py` are nearly identical copy-paste duplicates.

## Findings

**From:** code-simplicity-reviewer

**Location:** `backend/app/services/llm.py` lines 319-385, 388-458

**Current code pattern:**

```python
async def generate_provider_summary_content(...):
    user_prompt = build_provider_summary_user_prompt(...)
    raw = await self.provider.chat_completion(system=PROVIDER_SUMMARY_SYSTEM, ...)
    try:
        content = ProviderSummaryResponse(**json.loads(raw))
    except ...:
        raise DatabaseError(...)

async def generate_cheatsheet_content(...):
    user_prompt = build_cheatsheet_user_prompt(...)
    raw = await self.provider.chat_completion(system=CHEATSHEET_SYSTEM, ...)
    try:
        content = CheatsheetResponse(**json.loads(raw))
    except ...:
        raise DatabaseError(...)
```

**Estimated savings:** ~60 lines

## Proposed Solutions

### Option A: Extract Generic Helper (Recommended)

**Effort:** Low

```python
async def _generate_structured_content(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    context: str,
) -> T:
    """Generic structured content generator."""
    raw = await self.provider.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1000,
        temperature=0.4,
        response_format="json",
    )
    try:
        return response_model(**json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Failed to parse %s response: %s", context, exc)
        raise DatabaseError(f"Failed to parse {context}: {exc}") from exc

async def generate_provider_summary_content(...):
    user_prompt = build_provider_summary_user_prompt(...)
    return await self._generate_structured_content(
        PROVIDER_SUMMARY_SYSTEM,
        user_prompt,
        ProviderSummaryResponse,
        "provider summary",
    )
```

### Option B: Keep Separate Methods

**Risk:** More code to maintain, easier to diverge.

## Recommended Action

Implement Option A as post-merge cleanup.

## Technical Details

**Affected file:** `backend/app/services/llm.py`

## Acceptance Criteria

- [ ] Generic helper method created
- [ ] Both public methods refactored to use helper
- [ ] Tests still pass
- [ ] ~60 lines removed

## Work Log

| Date       | Action                         | Result  |
| ---------- | ------------------------------ | ------- |
| 2026-03-31 | Created from simplicity review | Pending |
