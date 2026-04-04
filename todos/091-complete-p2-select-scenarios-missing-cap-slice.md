---
status: pending
priority: p2
issue_id: "091"
tags: [code-review, backend, correctness, llm]
dependencies: []
---

# `_select_scenarios` comment says "cap at 7" but no `[:7]` slice present

## Problem Statement

The comment at `appointment.py:737` says "Deduplicate preserving order, cap at 7" but `return unique` has no `[:7]` slice. With more scenario groups or a future config change, this can silently return more than 7 scenarios, exceeding the LLM token budget. Tests pass only because the current fixture produces ≤7 scenarios.

## Findings

- **File**: `backend/app/services/appointment.py`, line ~737–743

```python
# Deduplicate preserving order, cap at 7
seen: set[str] = set()
unique: list[dict] = []
for s in scenarios:
    if s["title"] not in seen:
        unique.append(s)
        seen.add(s["title"])
return unique  # ← missing [:7]
```

- Test `test_result_has_at_most_7_scenarios` passes with current fixtures but would fail if `unique` grew beyond 7
- The performance oracle also flagged that 7 parallel RAG calls per `generate_scenarios` invocation assumes this cap

## Proposed Solution

```python
return unique[:7]
```

## Acceptance Criteria

- [ ] `_select_scenarios` returns `unique[:7]`
- [ ] Test `test_result_has_at_most_7_scenarios` still passes
- [ ] New test: when deduplicated list has 10 unique titles, result length is 7
