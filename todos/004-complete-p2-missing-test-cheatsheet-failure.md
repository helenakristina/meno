---
name: Add Missing Test for Cheatsheet Failure in asyncio.gather
status: complete
priority: p2
issue_id: 004
tags: [code-review, testing, error-handling]
dependencies: []
---

## Problem Statement

The parallelized LLM call code in `generate_pdf()` uses `asyncio.gather(provider_task, cheatsheet_task)` to run two calls concurrently. However, test coverage only exercises the **provider_summary_content failure path**, not the **cheatsheet_content failure path**.

**Test gap:**

- ✅ `test_raises_database_error_when_llm_times_out()` — Mocks TimeoutError on provider_task
- ❌ Missing test for TimeoutError on cheatsheet_task (the second task)
- ❌ Missing test for general Exception on cheatsheet_task

## Findings

**From:** performance-oracle

**Severity:** IMPORTANT (should fix before merge)

**Affected file:** `backend/tests/services/test_appointment_service.py`  
**Test class:** `TestGeneratePdf`  
**Location:** Lines 599-611 (existing timeout test), needs expansion

**Current code (lines 556-573 in appointment.py):**

```python
try:
    provider_summary_content, cheatsheet_content = await asyncio.gather(
        provider_task, cheatsheet_task
    )
except TimeoutError:
    logger.error(
        "LLM timed out during PDF content generation: appointment_id=%s",
        appointment_id,
    )
    raise DatabaseError("LLM request timed out generating PDF content")
except Exception as exc:
    logger.error(
        "LLM failed during PDF content generation: appointment_id=%s error=%s",
        appointment_id,
        exc,
        exc_info=True,
    )
    raise DatabaseError(f"Failed to generate PDF content: {exc}") from exc
```

The code correctly handles failures from **either task**, but tests only verify the first task failure.

## Proposed Solutions

### Option A: Add Two New Tests (Recommended)

**Effort:** Small  
**Risk:** None

Add to `TestGeneratePdf` class:

```python
async def test_raises_database_error_when_cheatsheet_times_out(self):
    """Test that timeout on cheatsheet_content is caught and converted to DatabaseError."""
    context = _make_context(goal=AppointmentGoal.PDF)
    self.supabase.save_appointment_context(context)
    self.supabase.save_narrative(context.id, context.user_id, "Generated narrative")

    # Mock the second task (cheatsheet) to timeout
    with patch.object(
        self.service.llm_service, "generate_cheatsheet_content",
        side_effect=TimeoutError("LLM request timed out")
    ):
        with patch.object(
            self.service.llm_service, "generate_provider_summary_content",
            return_value=_make_provider_response()
        ):
            with pytest.raises(DatabaseError, match="timed out"):
                await self.service.generate_pdf(context.id, context.user_id)

async def test_raises_database_error_when_cheatsheet_fails(self):
    """Test that non-timeout exception on cheatsheet_content is caught."""
    context = _make_context(goal=AppointmentGoal.PDF)
    self.supabase.save_appointment_context(context)
    self.supabase.save_narrative(context.id, context.user_id, "Generated narrative")

    # Mock the second task to raise a generic exception
    with patch.object(
        self.service.llm_service, "generate_cheatsheet_content",
        side_effect=ValueError("Invalid cheatsheet response")
    ):
        with patch.object(
            self.service.llm_service, "generate_provider_summary_content",
            return_value=_make_provider_response()
        ):
            with pytest.raises(DatabaseError, match="Failed to generate"):
                await self.service.generate_pdf(context.id, context.user_id)
```

This validates that:

- Timeout on the **second** task is caught and converted to DatabaseError
- Non-timeout exceptions on the **second** task are caught and converted to DatabaseError
- The error message is informative in both cases

## Recommended Action

Implement Option A: Add two new tests to `TestGeneratePdf` class covering cheatsheet failure paths.

## Technical Details

**Affected file:** `backend/tests/services/test_appointment_service.py`  
**Test class:** `TestGeneratePdf`  
**Current test count:** 8 tests  
**New test count:** 10 tests (8 + 2)

**Related code being tested:**

- `backend/app/services/appointment.py` lines 556-573 (generate_pdf error handling)

## Acceptance Criteria

- [ ] New test added for `generate_cheatsheet_content` TimeoutError
- [ ] New test added for `generate_cheatsheet_content` generic Exception
- [ ] Both tests verify DatabaseError is raised with appropriate message
- [ ] Both tests properly mock/patch the LLM service methods
- [ ] All 10 TestGeneratePdf tests pass
- [ ] All 52 appointment service tests pass (1039 baseline maintained)

## Work Log

| Date       | Action                                 | Result  |
| ---------- | -------------------------------------- | ------- |
| 2026-04-02 | Created from performance-oracle review | Pending |
