---
title: "Pydantic v2 model_fields_set for PATCH partial update semantics"
category: logic-errors
date: 2026-03-17
tags: [pydantic, fastapi, patch, api-design, python, backend]
---

# Pydantic v2 `model_fields_set` for PATCH partial update semantics

## Problem

PATCH endpoints that skip `None` values to support partial updates have a subtle bug: they cannot distinguish "field not included in request" from "field explicitly set to null (user wants to clear it)."

**Symptom:** Sending `{"has_uterus": null}` or `{"notes": null}` silently does nothing — the null value is dropped. The "Prefer not to say" option for `has_uterus` never saves. Clearing a notes field is impossible.

**Bug pattern:**

```python
# ❌ Broken — conflates "not provided" with "explicitly nulled"
if data.period_end is not None:
    update_data["period_end"] = data.period_end
if data.notes is not None:
    update_data["notes"] = data.notes
```

## Root Cause

The pattern `if value is not None: include_field` uses `None` to mean two different things:
- "This field was not in the PATCH body at all" (correct to skip)
- "This field was explicitly sent as `null` (user wants to clear it)" (must include)

## Solution

Use Pydantic v2's `model_fields_set` to check which fields were **explicitly provided** in the request, regardless of value:

```python
# ✅ Correct — uses model_fields_set to distinguish missing vs explicit null
update_data: dict = {}
if "period_end" in data.model_fields_set:
    update_data["period_end"] = data.period_end.isoformat() if data.period_end is not None else None
if "flow_level" in data.model_fields_set:
    update_data["flow_level"] = data.flow_level
if "notes" in data.model_fields_set:
    update_data["notes"] = data.notes
```

`model_fields_set` is populated by Pydantic at parse time and contains only the field names that were **present in the input payload**. Fields omitted from the request body are not in `model_fields_set`, even if they have default values.

### Applied to: `UserSettingsUpdate` (all three fields)

```python
# user_repository.py
update_data: dict = {}
if "period_tracking_enabled" in data.model_fields_set:
    update_data["period_tracking_enabled"] = data.period_tracking_enabled
if "has_uterus" in data.model_fields_set:
    update_data["has_uterus"] = data.has_uterus
if "journey_stage" in data.model_fields_set:
    update_data["journey_stage"] = data.journey_stage
```

### Applied to: `PeriodLogUpdate` (period_end, flow_level, notes)

```python
# period_repository.py
update_data: dict = {}
if "period_end" in data.model_fields_set:
    update_data["period_end"] = data.period_end.isoformat() if data.period_end is not None else None
if "flow_level" in data.model_fields_set:
    update_data["flow_level"] = data.flow_level
if "notes" in data.model_fields_set:
    update_data["notes"] = data.notes
```

## Business Rule Coercion at the Route Layer

When a PATCH also has a business rule that derives one field from another (e.g., `has_uterus=False → period_tracking_enabled=False`), apply the rule at the **route layer** before calling the repo. Rebuild the model using `model_validate` so `model_fields_set` is correctly updated:

```python
# routes/users.py — business rule applied before repo call
if "has_uterus" in payload.model_fields_set and payload.has_uterus is False:
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    fields["period_tracking_enabled"] = False
    payload = UserSettingsUpdate.model_validate(fields)
```

**Do not put business rules in repositories** — they should only execute what they're told.

## Prevention

- Any new PATCH endpoint with optional fields must use `model_fields_set`, not `is not None`.
- Business rules that derive one field from another belong in the route or service layer, not the repository.
- Add a test for the "explicit null clears field" case:

```python
async def test_update_settings_has_uterus_null():
    """has_uterus=None (prefer not to say) is saved when explicitly set."""
    data = UserSettingsUpdate.model_validate({"has_uterus": None})
    # model_fields_set = {"has_uterus"} — field IS included despite being null
    assert "has_uterus" in data.model_fields_set
```

## Files in this Codebase

- `backend/app/repositories/user_repository.py` — `update_settings()`
- `backend/app/repositories/period_repository.py` — `update_log()`
- `backend/app/api/routes/users.py` — `update_settings()` (business rule coercion)
- `backend/tests/repositories/test_user_repository.py` — `test_update_settings_has_uterus_null`
