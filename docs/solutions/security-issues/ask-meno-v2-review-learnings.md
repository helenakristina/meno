---
title: "Ask Meno v2: Code Review Learnings (Security, Architecture, Testing)"
category: security-issues
date: 2026-03-24
tags: [pii-logging, prompt-injection, llm-architecture, testing, pgvector, citations]
todos_resolved: [060, 061, 062, 063, 065, 066, 067, 068, 069, 070, 071]
---

# Ask Meno v2: Code Review Learnings

Eleven findings from the PR #4 code review of the v2 voice-forward response
schema. Documents recurring patterns worth remembering for future LLM feature
work.

---

## 1. Never log LLM response content at INFO level

**Problem:** `ask_meno.py` logged `json.dumps(raw_response)[:2000]` and
`response_text[:500]` at INFO on every request. LLM responses are derived from
the user's symptom context, medications, and health question — PHI by definition.

**Root cause:** Debug-era logging not removed before merge.

**Fix:** Replace any log that emits LLM-generated text with structural metadata:

```python
# ❌ logs PHI
logger.info("LLM response: %s", json.dumps(raw_response)[:2000])

# ✅ structural metadata only
logger.info(
    "Structured response for user=%s: sections=%d insufficient=%s disclaimer=%s",
    hash_user_id(user_id),
    len(raw_response.get("sections", [])),
    raw_response.get("insufficient_sources"),
    bool(raw_response.get("disclaimer")),
)
```

**Rule:** If the string contains anything the user typed or that an LLM generated
from their data, it must not appear in any log statement at any level.

---

## 2. User-supplied strings must be sanitized before system prompt injection

**Problem:** `PromptService.build_system_prompt()` injected medication fields
(name, dose, delivery method) directly into the system prompt via f-strings with
no sanitization. Any authenticated user could name a medication
`"Ignore all previous instructions..."` and inject it into Layer 5 of the
system prompt — after all guardrails.

**Root cause:** Trusted the database as a sanitized source; forgot the database
contains user-supplied strings.

**Fix:** Strip newlines and truncate before injection:

```python
@staticmethod
def _sanitize_prompt_field(value: str, max_len: int = 100) -> str:
    """Strip newlines and truncate to prevent prompt injection."""
    return value.replace("\n", " ").replace("\r", " ")[:max_len].strip()
```

Apply to: medication names (100), dose (50), delivery method (50), frequency
(50), symptom_summary (500).

**Rule:** Every user-supplied string that ends up in a system prompt must be
sanitized at the point of injection, regardless of how it was stored.

---

## 3. Hard-stop guards and JSON format rules cannot share a prompt layer

**Problem:** The prompt injection hard-stop ("respond only with: 'I can only
help with menopause...'") was moved into `LAYER_3_SOURCE_RULES`, which opens
with "You MUST respond ONLY with a valid JSON object." The guard emits plain
text. The two instructions directly contradict each other.

**Root cause:** The guard was moved from its v1 home (scope layer) to the format
layer during refactoring without noticing the conflict.

**Fix:** Move hard-stop guards to the scope/behavior layer (`LAYER_4_SCOPE`),
which contains no format constraints. The JSON rule stays in `LAYER_3`.

**Rule:** Each prompt layer should have a single concern. Format instructions
(JSON, structure) and behavioral guardrails (scope, hard-stops) must live in
separate layers.

---

## 4. Don't remove citation verification when refactoring response format

**Problem:** v1's `render_structured_response` ran `_claim_source_overlap` on
every claim. The v2 refactor removed this check from the primary path, leaving
the overlap check only in the fallback pipeline (triggered by JSON parse
failure). The LLM could now cite a topically adjacent but non-supporting source
with no detection.

**Root cause:** The verification logic wasn't explicitly ported when the
structured response format changed.

**Fix:** Add overlap logging to the primary path in `render_structured_response`:

```python
overlap = self._claim_source_overlap(section.body, chunk_content)
if overlap < self._RELEVANCE_MIN_OVERLAP:
    logger.warning(
        "render_structured_response: low overlap for section source_index=%d overlap=%.2f",
        idx, overlap,
    )
```

**Rule:** When changing a response pipeline (v1 → v2 format), explicitly audit
what safety/verification steps existed in the old path and confirm each one is
still present or deliberately removed.

---

## 5. Route tests must exercise the primary path, not just the fallback

**Problem:** `test_chat.py` mocked `chat_completion` to return plain text. When
`json.loads()` was called on it, `JSONDecodeError` fired and the fallback path
ran. All happy-path tests were silently exercising the fallback, not
`render_structured_response`.

**Root cause:** The mock was written before v2 added JSON-structured responses;
it was never updated.

**Fix:** Add a test with a valid v2 JSON mock response:

```python
V2_OPENAI_RESPONSE = json.dumps({
    "sections": [{"heading": "Hot Flashes", "body": "...", "source_index": 1}],
    "disclaimer": None,
    "insufficient_sources": False,
})
# mock chat_completion to return V2_OPENAI_RESPONSE
# assert response["message"] contains the body text
# assert response["citations"] is non-empty
```

**Rule:** When a service has multiple code paths (primary + fallback), each path
must have at least one route-level test. Check the mock return value matches the
format the primary path expects.

---

## 6. Use `extra="forbid"` to make regression tests pass by design

**Problem:** `ResponseSection` had no `model_config`. The v1 regression test
(`test_v1_json_format_triggers_fallback`) passed because v1 JSON was missing the
`body` field — not because extra v1 fields (`claims`, `source_indices`) were
explicitly rejected. A future `body: str = ""` default would silently break the
regression test.

**Fix:**

```python
class ResponseSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str | None = None
    body: str
    source_index: int | None = None
```

**Rule:** Schema regression tests should pass *by design*, not by the accident
of a currently-missing required field. `extra="forbid"` makes schema evolution
explicit and safe.

---

## 7. Always route LLM calls through the service layer

**Problem:** `AskMenoService.ask()` called `self.llm_service.provider.chat_completion()`
directly, bypassing `LLMService.chat_completion()`. All future guards (retry,
rate limiting, token caps) added to `LLMService` would silently not apply to
Ask Meno.

**Root cause:** `response_format="json"` wasn't supported by `LLMService` at the
time, so `.provider` was called directly as a workaround. The workaround was
never cleaned up.

**Fix:** Add the missing parameter to `LLMService` and remove the bypass:

```python
# In LLMService
async def chat_completion(
    self, system_prompt, user_prompt, response_format=None, ...
) -> str: ...

# In AskMenoService
response_text = await self.llm_service.chat_completion(
    system_prompt=system_prompt,
    user_prompt=message,
    response_format="json",
)
```

**Rule:** Never call `.provider` directly from a service. If `LLMService` is
missing a parameter you need, add it there — don't bypass the service layer.

---

## 8. Updating RAG retrieval tests when switching from Python to pgvector

**Context:** Hybrid RAG search (Python-side cosine similarity + RRF) was
replaced with pgvector similarity search via `supabase.rpc("match_rag_documents")`.
The old tests imported `_keyword_score` and `_reciprocal_rank_fusion` (now
deleted) and mocked `supabase.table().select().execute()` (now wrong).

**New mock pattern:**

```python
# get_client is now awaited — use AsyncMock
with patch("app.rag.retrieval.get_client", new_callable=AsyncMock) as mock_get_client:
    mock_supabase = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute = AsyncMock(return_value=MagicMock(data=SAMPLE_DOCS))
    mock_supabase.rpc.return_value = mock_rpc
    mock_get_client.return_value = mock_supabase
```

**Sample docs no longer have `embedding` field** — the RPC returns `similarity`
directly. `hybrid_score` is also gone.

**Tests to keep:** empty result, similarity threshold filtering, RPC called with
correct `match_count`, response structure fields, OpenAI/Supabase error propagation.

**Tests to remove:** anything testing Python-side keyword scoring, RRF, embedding
parsing, or `hybrid_score`.

---

## Prevention Checklist for Future LLM Features

Before merging any PR that touches the LLM pipeline:

- [ ] No log statements emit LLM-generated text or user health data
- [ ] All user-supplied strings passed to system prompts go through `_sanitize_prompt_field`
- [ ] Hard-stop guards live in the scope layer, not the format layer
- [ ] Citation/source verification is present on the primary response path
- [ ] Route tests cover the primary happy path, not just fallback paths
- [ ] Pydantic models for LLM output use `extra="forbid"`
- [ ] All LLM calls go through `LLMService.chat_completion()`, not `.provider` directly
- [ ] Stale comments describing temperature/behavior are updated when values change
