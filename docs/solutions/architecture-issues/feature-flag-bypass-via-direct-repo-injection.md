---
title: Feature flag bypassed when service injects repository from another domain directly
category: architecture-issues
date: 2026-03-18
tags: [feature-flag, dependency-injection, service-layer, architecture, medications]
modules: [medications, appointment, export, services]
problem_type: architecture-issue
---

# Feature flag bypassed when service injects repository from another domain directly

## Problem

`AppointmentService` and `ExportService` both accepted `medication_repo: Optional[MedicationRepository]` as a constructor argument and called it directly. The `mht_tracking_enabled` feature flag check lived in `MedicationService.list_current` — not in `MedicationRepository`. By calling the repository directly, both services bypassed the flag entirely.

A user who disabled MHT tracking in settings would still see their medications appear in appointment prep narratives and PDF exports.

**Symptom:** Feature flag disabled, but medication data still appears in outputs from services that call the repo directly.

## Root Cause

When adding medication context to existing services, the repo was injected directly following the general "services call repos" pattern. The developer didn't realize the feature flag logic lived one layer up — in `MedicationService` — not in the repository.

`MedicationRepository` has no awareness of user settings. It just returns rows. The flag check is a business rule that belongs in `MedicationService`, but only callers who go through the service get that check for free.

```python
# AppointmentService before fix — bypasses mht_tracking_enabled
class AppointmentService:
    def __init__(self, ..., medication_repo: Optional[MedicationRepository] = None):
        self.medication_repo = medication_repo

    async def generate_narrative(self, user_id):
        if self.medication_repo:
            medications = await self.medication_repo.list_current(user_id)  # no flag check!
```

## Solution

Replace the `MedicationRepository` dependency with `MedicationServiceBase` (the ABC). The service-to-service call still routes through `MedicationRepository` internally — the call chain is:

```
AppointmentService
  → MedicationService.list_current()   ← flag check lives HERE
    → MedicationRepository.list_current()
      → Database
```

No repository is bypassed. You're just adding a domain boundary in between that owns the business rules for that domain.

```python
# AppointmentService after fix
from app.services.medication_base import MedicationServiceBase

class AppointmentService:
    def __init__(self, ..., medication_service: Optional[MedicationServiceBase] = None):
        self.medication_service = medication_service

    async def generate_narrative(self, user_id):
        if self.medication_service:
            medications = await self.medication_service.list_current(user_id)  # flag respected
```

Update `dependencies.py` to wire `MedicationService` (not `MedicationRepository`) into both services:

```python
# dependencies.py
def get_appointment_service(
    ...
    medication_service: MedicationService = Depends(get_medication_service),  # ← service, not repo
) -> AppointmentService:
    return AppointmentService(..., medication_service=medication_service)
```

## Key Insight

> **"Service-to-service dependency doesn't bypass repositories"** — it just adds a domain service layer in between. `ServiceA → ServiceB → Repository → DB` is still repository-based access. The repository is still the only thing that talks to the database.

The rule of thumb: **when a service needs data from another domain, depend on that domain's `ServiceBase` ABC, not its repository.** The repository is for intra-domain data access only.

## Prevention

- When adding cross-domain data fetching to a service, always ask: "does the domain I'm reading from have business rules (feature flags, access controls, computed fields) that live in its service layer?"
- If yes → inject the `ServiceBase`, not the `Repository`
- If the `ServiceBase` doesn't have the method you need, add it — that's a signal the method belongs there

### Checklist for cross-domain service integration

- [ ] Am I injecting a `Repository` from a different domain? (red flag)
- [ ] Does the domain service have feature flag checks, auth gates, or derived data logic?
- [ ] Is the `ServiceBase` ABC the right dependency instead?
- [ ] Are all callers of this data going through the same flag/rule enforcement?

## Related

- `docs/solutions/architecture-issues/idor-regression-test-pattern.md` — complementary: ownership enforcement in repositories
- PR #2 todos: 042 (the fix), 039–059 (full medication tracking code review)
- Files changed: `backend/app/services/appointment.py`, `backend/app/services/export.py`, `backend/app/services/medication_base.py`, `backend/app/api/dependencies.py`
