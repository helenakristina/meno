---
status: complete
priority: p2
issue_id: "045"
tags: [code-review, architecture, backend, medications, pr-2]
dependencies: []
---

# `ValidationError` raised in repository — business logic in wrong layer

## Problem Statement

`MedicationRepository.change_dose` catches a Postgres error string and raises a domain `ValidationError` via a lazy import inside the exception handler. Business rule validation belongs in the service layer. The repository should only raise `DatabaseError` or `EntityNotFoundError`.

## Findings

- `backend/app/repositories/medication_repository.py` lines 329–333
- Lazy import: `from app.exceptions import ValidationError` inside the except block
- The `effective_date > start_date` check is **already validated** in `MedicationService.change_dose` lines 129–130 before the RPC is ever called
- This duplicate check in the repository means two places enforce the same invariant with potentially different error messages
- Repositories should only translate DB errors → `DatabaseError` or `EntityNotFoundError`
- Identified by Python reviewer and architecture-strategist

## Proposed Solutions

### Option 1: Remove the `ValidationError` branch from the repository (Recommended)

The RPC error `"effective_date_before_start"` will only be triggered if the service-layer guard is bypassed (impossible in normal flow). Remove the branch and let it fall through to `DatabaseError`:

```python
except Exception as exc:
    msg = str(exc)
    if "medication_not_found" in msg:
        raise EntityNotFoundError("Medication not found") from exc
    raise DatabaseError("Failed to change medication dose") from exc
```

Also move the lazy import to the top of the file (or remove it entirely if `ValidationError` is no longer used in the repo).

**Pros:** Correct layering, single source of truth for this business rule
**Effort:** Small
**Risk:** None — service-layer guard prevents the RPC from seeing invalid dates

## Recommended Action

Option 1 — remove the branch, keep service-layer guard as the sole enforcer.

## Technical Details

**Affected files:**
- `backend/app/repositories/medication_repository.py` lines 325–335

## Acceptance Criteria

- [ ] No `ValidationError` raised or imported in any repository file
- [ ] `change_dose` only raises `EntityNotFoundError` or `DatabaseError`
- [ ] `MedicationService.change_dose` test for `effective_date < start_date` still passes

## Work Log

- 2026-03-18: Identified by Python reviewer and architecture-strategist in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
