---
status: pending
priority: p3
issue_id: "095"
tags: [code-review, backend, architecture, maintainability]
dependencies: []
---

# `save_narrative` and `save_qualitative_context` routes call repository directly

## Problem Statement

Both new PUT routes call `appointment_repo` methods directly from the route handler, bypassing `AppointmentService`. Every other step that does meaningful work goes through the service layer. This inconsistency means future additions (audit logging, sanitization, business rules) will land in the route handler rather than the service.

## Findings

- **File**: `backend/app/api/routes/appointment.py`
  - `save_narrative` (line ~168): calls `appointment_repo.get_context` + `appointment_repo.save_narrative` inline
  - `save_qualitative_context` (line ~218): calls `appointment_repo.get_context` + `appointment_repo.save_qualitative_context` inline
- The project convention per `AppointmentService` docstring: "No HTTP concerns — raises domain exceptions which routes convert to HTTP responses"
- `AppointmentService` already has access to the repo via `self.appointment_repo`

## Proposed Solution

Add thin delegating methods to `AppointmentService`:

```python
async def save_narrative(self, appointment_id: str, user_id: str, narrative: str) -> None:
    await self.appointment_repo.get_context(appointment_id, user_id)  # ownership check
    await self.appointment_repo.save_narrative(appointment_id, user_id, narrative)

async def save_qualitative_context(self, appointment_id: str, user_id: str, ctx: QualitativeContext) -> None:
    await self.appointment_repo.get_context(appointment_id, user_id)  # ownership check
    await self.appointment_repo.save_qualitative_context(...)
```

Routes then call `appointment_service.save_narrative(...)` etc.

## Acceptance Criteria

- [ ] `save_narrative` route delegates to `appointment_service.save_narrative()`
- [ ] `save_qualitative_context` route delegates to `appointment_service.save_qualitative_context()`
- [ ] Service methods added with existing tests still passing
- [ ] Route handler stays thin (ownership verification + HTTP conversion only)
