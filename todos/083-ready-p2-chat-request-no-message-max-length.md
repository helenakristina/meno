---
status: pending
priority: p2
issue_id: "083"
tags: [code-review, security, backend, chat, pr-10]
dependencies: []
---

# ChatRequest.message has no max_length — cost amplification and prompt injection risk

## Problem Statement

`backend/app/models/chat.py` defines `ChatRequest.message: str` with no `max_length`. A malicious or erroneous client can submit arbitrarily large payloads. This has two direct consequences:

1. **Prompt injection amplification:** A very long message can overwhelm the system prompt layers, reducing the effectiveness of the medical advice guardrails. The longer the user message relative to the system prompt, the higher the probability adversarial instructions succeed.

2. **API cost amplification:** Every byte is tokenized and billed. A 50,000-character message consumes ~12,500 input tokens per call. With no rate limiting on `/api/chat`, this can be triggered repeatedly.

## Findings

- `backend/app/models/chat.py` lines 43–48: `message: str = Field(description="The user's question")` — no `max_length`
- No per-user rate limiting on the `/api/chat` endpoint
- Identified by security-sentinel (second pass)

## Proposed Solutions

### Option 1: Add max_length + rate limiting (Recommended)

**Step 1 — Field constraint:**
```python
message: str = Field(description="The user's question", min_length=1, max_length=2000)
```

**Step 2 — Rate limiting** (per user, 20 req/min is reasonable for a conversational interface):
Add `slowapi` or a Supabase-level RLS policy on conversation creation frequency.

**Pros:** Directly limits blast radius for both injection and cost attacks
**Effort:** Small (Step 1 is a one-liner; Step 2 is Medium)
**Risk:** Low — real users rarely type more than 500 characters per message

## Recommended Action

Step 1 immediately (one-liner, no risk). Step 2 before production deployment.

## Technical Details

- `backend/app/models/chat.py`
- Pair with a test: `test_chat_request_rejects_message_over_2000_chars`

## Acceptance Criteria

- [ ] `ChatRequest.message` has `max_length=2000`
- [ ] `ChatRequest.message` has `min_length=1`
- [ ] Test covers the max_length validation
- [ ] API returns 422 with clear error when message exceeds limit

## Work Log

- 2026-03-25: Identified by security-sentinel (second pass) in PR #10 review
