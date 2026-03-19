---
status: complete
priority: p1
issue_id: "042"
tags: [code-review, architecture, backend, medications, feature-flag, pr-2]
dependencies: []
---

# MHT feature flag bypassed in AppointmentService and ExportService

## Problem Statement

`AppointmentService` and `ExportService` both hold a direct `MedicationRepository` reference and call repository methods directly, bypassing the `mht_tracking_enabled` feature flag check that lives in `MedicationService`. A user who disables MHT tracking will still see their medications in appointment prep narratives and PDF exports.

## Findings

- `backend/app/services/appointment.py` lines 53–61 — accepts `medication_repo: Optional[MedicationRepository]`, calls `self.medication_repo.list_current(user_id)` directly (line 178–186)
- `backend/app/services/export.py` line 131 — calls `medication_repo.list_active_during(...)` directly
- `MedicationService.list_current` (line 79–84 in `medication.py`) checks `mht_tracking_enabled` and returns `[]` if disabled — this check is bypassed
- `MedicationService.get_context_if_enabled` also respects the feature flag — also bypassed
- Confirmed by architecture-strategist and security-sentinel

## Proposed Solutions

### Option 1: Inject `MedicationServiceBase` instead of `MedicationRepository` (Recommended)

**Important:** this still keeps all DB calls going through `MedicationRepository` — `MedicationService` calls the repo internally. The call chain is:

```
AppointmentService → MedicationService.get_context_if_enabled()
                           ↓  (flag check lives here — one place)
                     MedicationRepository.get_context()
                           ↓
                        Database
```

In `AppointmentService`:
```python
# Instead of: medication_repo: Optional[MedicationRepository] = None
medication_service: Optional[MedicationServiceBase] = None

# Instead of: self.medication_repo.list_current(user_id)
context = await self.medication_service.get_context_if_enabled(user_id)
```

In `ExportService`, same pattern. Update `dependencies.py` to wire `MedicationService` into both.

**Pros:** All DB access still goes through `MedicationRepository`. Flag check lives in exactly one place (`MedicationService`). All three callers automatically respect it.
**Effort:** Small — parameter rename + DI wiring + update tests
**Risk:** Low

### Option 2: Add explicit inline flag check before each repo call

Keeps the direct repo reference but adds `user_repo.get_settings()` before each call.

**Cons:** Flag logic duplicated in 3 places — if behavior changes, update 3 files
**Effort:** Small
**Risk:** Low but creates tech debt

## Recommended Action

Option 1 — the DB call still goes through `MedicationRepository`, just routed via `MedicationService` so the flag logic is centralized.

## Technical Details

**Affected files:**
- `backend/app/services/appointment.py`
- `backend/app/services/export.py`
- `backend/app/api/dependencies.py` (DI wiring update)
- `backend/tests/services/test_appointment_service.py` (update mocks)

## Acceptance Criteria

- [ ] User with `mht_tracking_enabled=False`: appointment narrative contains no medication context
- [ ] User with `mht_tracking_enabled=False`: PDF export contains no medication section
- [ ] User with `mht_tracking_enabled=True`: both still receive medication context
- [ ] `AppointmentService` and `ExportService` no longer import `MedicationRepository` directly

## Work Log

- 2026-03-18: Identified by architecture-strategist and security-sentinel in PR #2 code review
- 2026-03-18: Approved during triage — clarified that Option 1 still routes DB calls through MedicationRepository (service-to-service doesn't bypass repo layer)

## Resources

- PR #2: feat/mht-medication-tracking
- `backend/app/services/appointment.py`
- `backend/app/services/export.py`
- `backend/app/services/medication_base.py` (interface to depend on)
