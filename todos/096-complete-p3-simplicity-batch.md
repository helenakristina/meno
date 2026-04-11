---
status: pending
priority: p3
issue_id: "096"
tags: [code-review, backend, simplicity, types]
dependencies: []
---

# Simplicity batch: deserialization duplication, rag_chunks no-op, ScenarioSource model

## Problem Statement

Three small simplicity issues identified by the code-simplicity-reviewer and architecture-strategist that create maintenance friction without adding value.

## Findings

### 1. Concern deserialization duplicated in service and repository

`generate_pdf` in `appointment.py` (lines 538–543) reimplements the same `str` → `Concern` / `dict` → `Concern` backward-compat logic that `get_concerns()` in the repository already handles. Two sources of truth for backward compatibility.

**Fix**: in `generate_pdf`, call `self.appointment_repo.get_concerns(appointment_id, user_id)` instead of `appointment_data.get("concerns")` + inline deserialization. The repository method already handles both old and new formats.

### 2. `rag_chunks or None` is a no-op — `llm.py` line 313

```python
rag_chunks=rag_chunks or None,
```

`rag_chunks` is `list[dict] | None`. `[] or None` collapses to `None`, but the prompt builder already guards with `if rag_chunks:`. Passing `None` vs `[]` produces identical behaviour. Remove or add a comment explaining the intent.

### 3. `ScenarioCard.sources` should be `list[ScenarioSource]` not `list[dict]`

The frontend TS type already defines `sources?: Array<{ title: string; excerpt: string }>`. The backend has no enforcement. A `ScenarioSource(BaseModel)` would validate LLM output at parse time, matching how `ProviderSummaryResponse` and `CheatsheetResponse` work.

```python
class ScenarioSource(BaseModel):
    title: str
    excerpt: str

class ScenarioCard(BaseModel):
    ...
    sources: list[ScenarioSource] = Field(default_factory=list)
```

## Acceptance Criteria

- [ ] `generate_pdf` uses `get_concerns()` instead of inline deserialization (removes ~6 lines)
- [ ] `rag_chunks or None` removed or documented
- [ ] `ScenarioSource` model created; `ScenarioCard.sources` typed as `list[ScenarioSource]`
- [ ] Frontend `ScenarioCard` type updated to match (or already matches)
- [ ] All 1070 backend tests still pass
