---
name: HTTP-Level Input Validation for urgent_symptom
status: complete
priority: p2
issue_id: 003
tags: [code-review, security, validation]
dependencies: []
---

## Problem Statement

The `CreateAppointmentContextRequest` model in `backend/app/models/appointment.py` accepts `urgent_symptom: str | None` with **no validation constraints** at the HTTP boundary.

**Current code (lines 193-196):**

```python
class CreateAppointmentContextRequest(BaseModel):
    urgent_symptom: str | None = Field(
        default=None,
        description="Which symptom is urgent (only set when goal is 'urgent_symptom')",
    )
    # ❌ No max_length, no pattern, no constraints
```

**Risk:**

- A client could send a 10MB `urgent_symptom` value
- Pydantic accepts it at the HTTP layer without validation
- Service-layer sanitization in `AppointmentService._sanitize_urgent_symptom()` catches it, but defense-in-depth principle violated
- Validation should occur at EVERY layer: HTTP boundary, business logic, prompt injection point

## Findings

**From:** security-sentinel

**Severity:** IMPORTANT (should fix before merge)

**Affected file:** `backend/app/models/appointment.py` lines 193-196

**Defense-in-depth violation:**
Current flow:

1. HTTP request accepts unbounded `urgent_symptom` ❌
2. Route handler receives it
3. Service layer sanitizes it via `_sanitize_urgent_symptom()` ✅
4. Keyword matching uses sanitized value ✅

Better flow:

1. HTTP layer validates length (max 500 chars) ✅
2. Route handler receives validated data
3. Service layer further sanitizes ✅
4. Keyword matching uses doubly-filtered value ✅

## Proposed Solutions

### Option A: Pydantic Field Constraints (Recommended)

**Effort:** Small  
**Risk:** Low

```python
from pydantic import Field, StringConstraints
from typing import Annotated

class CreateAppointmentContextRequest(BaseModel):
    appointment_type: AppointmentType
    goal: AppointmentGoal
    dismissed_before: DismissalExperience
    urgent_symptom: str | None = Field(
        default=None,
        max_length=500,  # Reasonable limit for symptom description
        description="Which symptom is urgent (max 500 chars)"
    )
```

Pydantic will reject any request with `urgent_symptom` > 500 chars at validation time, returning HTTP 422 Unprocessable Entity with clear error.

### Option B: Regex Pattern Validation

**Effort:** Small  
**Risk:** Medium (may be too restrictive)

```python
urgent_symptom: str | None = Field(
    default=None,
    max_length=500,
    pattern=r"^[\w\s\-(),.]*$",  # Only alphanumeric, spaces, common punctuation
    description="Which symptom is urgent (alphanumeric + spaces/punctuation only)"
)
```

Note: This duplicates the character filtering in `_sanitize_urgent_symptom()`. Not recommended — keep HTTP validation simple (length only), service handles character filtering.

## Recommended Action

Implement Option A: Add `max_length=500` constraint to `urgent_symptom` field in `CreateAppointmentContextRequest`.

This provides defense-in-depth without duplicating business logic across layers.

## Technical Details

**Affected file:** `backend/app/models/appointment.py`  
**Class:** `CreateAppointmentContextRequest`  
**Field:** `urgent_symptom`

**Related service-layer code:**

- `backend/app/services/appointment.py` line 633-649: `_sanitize_urgent_symptom()` already limits to 200 chars
- Setting HTTP limit to 500 chars allows service layer to trim to 200 — no conflict

## Acceptance Criteria

- [ ] `urgent_symptom` field has `max_length=500` constraint
- [ ] HTTP request with 501+ char symptom returns HTTP 422 with validation error
- [ ] Existing valid requests (< 500 chars) still work
- [ ] Service layer `_sanitize_urgent_symptom()` still trims to 200 chars
- [ ] All appointment tests pass (1039 baseline)
- [ ] No breaking change to existing clients (all legitimate symptoms < 500 chars)

## Work Log

| Date       | Action                                | Result  |
| ---------- | ------------------------------------- | ------- |
| 2026-04-02 | Created from security-sentinel review | Pending |
