---
name: Use Pydantic model_dump() for JSON Serialization
status: complete
priority: p3
tags: [code-review, refactor, code-quality]
dependencies: []
---

## Problem Statement

Manual dict construction for stats serialization in `appointment.py` is verbose and duplicates model knowledge.

## Findings

**From:** code-simplicity-reviewer

**Location:** `backend/app/services/appointment.py` lines 260-291

**Current verbose code:**

```python
freq_stats_json = [
    {
        "symptom_id": s.symptom_id,
        "symptom_name": s.symptom_name,
        "category": s.category,
        "count": s.count,
    }
    for s in frequency_stats
]
```

## Proposed Solutions

### Option A: Use model_dump() (Recommended)

**Effort:** Small

```python
freq_stats_json = [s.model_dump() for s in frequency_stats]
coocc_stats_json = [p.model_dump() for p in cooccurrence_stats]
```

### Option B: Keep Current (More Explicit)

**Risk:** More code to maintain when models change.

## Recommended Action

Implement Option A. The Pydantic models already define the serialization structure.

## Technical Details

**Affected file:** `backend/app/services/appointment.py`
**Method:** `generate_narrative()`

**Note:** Ensure models are Pydantic v2 compatible with `model_dump()`.

## Acceptance Criteria

- [ ] Use `model_dump()` instead of manual dict construction
- [ ] ~20 lines removed
- [ ] Tests still pass

## Work Log

| Date       | Action                         | Result  |
| ---------- | ------------------------------ | ------- |
| 2026-03-31 | Created from simplicity review | Pending |
