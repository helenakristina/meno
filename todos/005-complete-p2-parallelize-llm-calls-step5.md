---
name: Parallelize Step 5 LLM Calls
status: complete
priority: p2
tags: [code-review, performance, async]
dependencies: []
---

## Problem Statement

PDF generation Step 5 makes 2 sequential LLM calls, causing 4-6 second wait time instead of 2-3 seconds.

## Findings

**From:** performance-oracle

**Location:** `backend/app/services/appointment.py` lines 534-581

**Current sequential calls:**

1. `generate_provider_summary_content()` (lines 536-556)
2. `generate_cheatsheet_content()` (lines 560-581)

**Impact:** If LLM takes 2-3 seconds per call, total wait is 4-6 seconds for Step 5.

## Proposed Solutions

### Option A: Use asyncio.gather() (Recommended)

**Effort:** Small
**Risk:** Low

```python
# Optimization:
provider_task = self.llm_service.generate_provider_summary_content(...)
cheatsheet_task = self.llm_service.generate_cheatsheet_content(...)

provider_summary_content, cheatsheet_content = await asyncio.gather(
    provider_task, cheatsheet_task
)
```

### Option B: Keep Sequential

**Risk:** Slower user experience, but simpler error handling.

## Recommended Action

Implement Option A. The calls are independent and safe to parallelize.

## Technical Details

**Affected file:** `backend/app/services/appointment.py`
**Method:** `generate_pdf()`

**Note:** Error handling must aggregate exceptions from both calls.

## Acceptance Criteria

- [ ] Both LLM calls run in parallel
- [ ] Error handling works for both success and failure cases
- [ ] Total latency reduced (should see ~40% improvement)
- [ ] Unit tests updated

## Work Log

| Date       | Action                         | Result  |
| ---------- | ------------------------------ | ------- |
| 2026-03-31 | Created from performance audit | Pending |
