---
status: complete
priority: p2
issue_id: "127"
tags: [code-review, security, prompt-injection, context-builder]
---

# `journey_stage` from DB injected into system prompt without sanitization

## Problem Statement

`backend/app/utils/context_builder.py` line 114:

```python
f"- Journey stage: {journey_stage}\n"
```

`journey_stage` is read from the `users` table as a raw string (`row.get("journey_stage") or "unsure"` in `user_repository.py`). The value is typed as `Literal["perimenopause", "menopause", "post-menopause", "unsure"]` but Pydantic validation is not applied at the repository return point — it is returned as a plain string.

If the DB value is corrupted (migration bug, admin tool direct write, or future vulnerability elsewhere), an attacker-controlled string would land in the system prompt without sanitization. Lower probability than the RAG chunk vector, but same consequence.

Compare: every medication field is sanitized; `symptom_summary` is sanitized; `journey_stage` is not.

## Proposed Solution

**Option A — Sanitize in ContextBuilder (consistent with other fields):**

```python
f"- Journey stage: {sanitize_prompt_input(journey_stage, max_length=50)}\n"
```

**Option B — Allowlist at repository:**

In `user_repository.py`, normalize the value after DB read:

```python
VALID_STAGES = {"perimenopause", "menopause", "post-menopause", "unsure"}
journey_stage = row.get("journey_stage") or "unsure"
if journey_stage not in VALID_STAGES:
    journey_stage = "unsure"
```

Option A is one line and keeps the defense at the prompt-building layer. Option B is more correct architecturally (validate at the boundary) and makes `journey_stage` safe everywhere it's used.

**Effort:** Small  
**Risk:** None

## Acceptance Criteria

- [ ] `journey_stage` is either sanitized before insertion into the prompt OR validated against the allowed set at the repository layer
- [ ] A value not in the four known stages does not appear verbatim in the prompt

## Work Log

- 2026-04-15: Identified by PR #25 code review (security-sentinel)
