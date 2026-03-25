---
status: complete
priority: p2
issue_id: "068"
tags: [code-review, testing, ask-meno, coverage]
dependencies: []
---

# Route tests only exercise the fallback path — structured v2 path has zero route-level coverage

## Problem Statement

`backend/tests/api/routes/test_chat.py` mocks `chat_completion` to return a plain text string (`OPENAI_RESPONSE`). When `ask_meno.py` calls `json.loads(response_text)`, this raises `JSONDecodeError`, triggering the fallback pipeline. All happy-path route tests now exercise the fallback, not the v2 structured path.

This means the primary code path (`render_structured_response` with v2 JSON) has no route-level integration test. A bug in how paragraph output flows through to `ChatResponse.message` would not be caught.

## Findings

- `backend/tests/api/routes/test_chat.py:OPENAI_RESPONSE` — plain text string, triggers fallback
- `backend/app/services/ask_meno.py:296–320` — fallback triggered on `JSONDecodeError`
- `render_structured_response` route-level coverage: 0 tests
- Confirmed by: architecture-strategist

## Proposed Solutions

### Add one route test with a valid v2 JSON mock response

```python
V2_OPENAI_RESPONSE = json.dumps({
    "sections": [
        {
            "heading": "Hot Flashes",
            "body": "Hot flashes are one of the most common symptoms of perimenopause.",
            "source_index": 1,
        }
    ],
    "disclaimer": None,
    "insufficient_sources": False,
})

async def test_chat_structured_v2_path(client, ...):
    # mock chat_completion to return V2_OPENAI_RESPONSE
    # assert response message contains "Hot flashes"
    # assert response citations has one entry
```

**Effort:** Small.

## Acceptance Criteria

- [ ] At least one route test uses a valid v2 JSON response from the mocked LLM
- [ ] That test asserts on `message` (contains prose paragraph) and `citations` (non-empty)
- [ ] All tests pass

## Work Log

- 2026-03-23: Found by architecture-strategist in PR #4 review
- 2026-03-24: Approved during triage session. Status changed pending → ready.
