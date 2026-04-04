---
status: pending
priority: p2
issue_id: "093"
tags: [code-review, backend, performance, llm, rag]
dependencies: []
---

# RAG chunks not deduplicated before LLM call — inflated prompt tokens

## Problem Statement

`generate_scenarios` runs parallel RAG retrieval (one embedding call per scenario title, up to 7), then flat-merges all results. When multiple scenario titles retrieve the same underlying document, duplicate chunks inflate the LLM prompt up to 35 chunks (7 scenarios × 5 top_k). This burns unnecessary tokens and at worst causes `sanitize_prompt_input`'s 2000-char ceiling to truncate real scenario content.

## Findings

- **File**: `backend/app/services/appointment.py`, lines 353–373

```python
chunk_results = await asyncio.gather(
    *[self.rag_retriever(s["title"], top_k=5, ...) for s in scenarios_to_generate]
)
for chunks in chunk_results:
    all_rag_chunks.extend(chunks)  # no dedup — same chunk can appear N times
```

- With 7 scenarios covering overlapping topics (e.g., multiple dismissal scenarios about HRT), the same NAMS guideline chunk will appear 3–5× in `all_rag_chunks`
- `all_rag_chunks` is passed directly to `build_scenario_suggestions_user_prompt`, which formats all of them as "Source documents"

## Proposed Solution

Deduplicate by chunk `id` after the gather, and cap total chunks sent to the LLM:

```python
seen_ids: set[str] = set()
deduped: list[dict] = []
for chunk in all_rag_chunks:
    if chunk.get("id") not in seen_ids:
        deduped.append(chunk)
        seen_ids.add(chunk.get("id"))
all_rag_chunks = deduped[:12]  # cap at 12 regardless of scenario count
```

## Acceptance Criteria

- [ ] Duplicate chunks (same `id`) are removed after the gather
- [ ] Total chunks passed to LLM capped at a reasonable maximum (10–15)
- [ ] Test: when two scenarios retrieve the same chunk, it appears only once in the LLM call args
- [ ] Test: deduplication does not affect scenarios that have unique sources
