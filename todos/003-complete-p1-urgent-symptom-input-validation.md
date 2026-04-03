---
name: urgent_symptom Input Validation
status: complete
priority: p1
tags: [code-review, security, validation]
dependencies: []
---

## Problem Statement

The `urgent_symptom` field from user input is used directly in keyword matching without validation or sanitization, potentially allowing DoS via extremely long input.

## Findings

**From:** security-sentinel

**Location:** `backend/app/services/appointment.py` lines 678-693 (`_select_scenarios`)

**Vulnerable code:**

```python
symptom_lower = urgent_symptom.lower()
for group in config["symptom_scenarios"].values():
    if any(kw in symptom_lower for kw in group["keywords"]):
        scenarios.extend(group["dismissals"])
```

**Risk:** A maliciously crafted `urgent_symptom` could:

- Be extremely long (DoS via memory consumption)
- Contain unexpected characters affecting downstream processing
- Cause performance issues in substring matching

## Proposed Solutions

### Option A: Add Input Validation (Recommended)

**Effort:** Small
**Risk:** Low

Add validation at the service layer:

```python
def _sanitize_urgent_symptom(self, symptom: str | None) -> str | None:
    """Sanitize urgent_symptom input."""
    if not symptom:
        return None
    # Limit length
    symptom = symptom[:200]
    # Allow only alphanumeric, spaces, and common punctuation
    symptom = re.sub(r'[^\w\s\-(),.]', '', symptom)
    return symptom.strip()
```

Call this at the start of `_select_scenarios` before using `urgent_symptom`.

### Option B: Validate at API Layer

**Effort:** Small
Add Pydantic validator on the request model to limit length and characters.

## Recommended Action

Implement Option A in the service layer for defense in depth.

## Technical Details

**Affected file:** `backend/app/services/appointment.py`
**Method:** `_select_scenarios`

## Acceptance Criteria

- [ ] Input validation added for `urgent_symptom`
- [ ] Length limited to reasonable maximum (200 chars)
- [ ] Character filtering applied
- [ ] Unit tests for validation edge cases (empty, too long, special chars)

## Work Log

| Date       | Action                      | Result  |
| ---------- | --------------------------- | ------- |
| 2026-03-31 | Created from security audit | Pending |
