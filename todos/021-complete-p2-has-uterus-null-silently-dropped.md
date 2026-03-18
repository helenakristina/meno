---
status: pending
priority: p2
issue_id: "021"
tags: [code-review, backend, bug, data-integrity]
dependencies: [010]
---

# Fix `has_uterus=null` silently dropped — "Prefer not to say" never saves

## Problem Statement

The settings page offers a "Prefer not to say" radio option for `has_uterus` that calls `saveHasUterus(null)`. This sends `{"has_uterus": null}` in the PATCH body. Pydantic parses it as `None` on `UserSettingsUpdate.has_uterus`, and then `user_repository.update_settings` skips it because of the `if data.has_uterus is not None` guard. The value never changes. "Prefer not to say" is silently ignored — a functional bug.

The `None`-skip pattern was written to mean "field not provided" (partial update semantics), but it conflates "not provided" with "explicitly set to null."

## Findings

- `backend/app/repositories/user_repository.py:284` — `if data.has_uterus is not None: update_data["has_uterus"] = data.has_uterus`
- `frontend/src/routes/(app)/settings/+page.svelte` — "Prefer not to say" radio sends `null`
- Code simplicity reviewer flagged this as a functional bug
- Same issue exists for `period_end` in period logs (covered separately in todo 008)

## Proposed Solutions

### Option 1: Use `model_fields_set` (consistent with todo 008)

**Approach:**
```python
if "has_uterus" in data.model_fields_set:
    update_data["has_uterus"] = data.has_uterus  # None = clear to "prefer not to say"
```

Apply the same `model_fields_set` pattern to all three fields in `update_settings`.

**Pros:** Standard Pydantic v2 approach, consistent with fix in `update_log` (todo 008)

**Cons:** None

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Use string enum instead of nullable boolean

**Approach:** Change `has_uterus` from `bool | None` to `Literal["yes", "no", "prefer_not_to_say"] | None`. Removes the sentinel problem entirely and is more self-documenting.

**Pros:** No sentinel needed, clearly expressive, DB CHECK constraint is readable

**Cons:** DB migration needed to change column type, frontend changes needed

**Effort:** 1-2 hours

**Risk:** Medium (DB + frontend + backend change)

## Recommended Action

Option 1 as an immediate fix (consistent with todo 008 approach). Option 2 is a better long-term model but is a larger change.

## Technical Details

**Affected files:**
- `backend/app/repositories/user_repository.py` — `update_settings` method
- `backend/tests/repositories/test_user_repository.py` — add test for null has_uterus save

## Acceptance Criteria

- [ ] `PATCH /api/users/settings` with `{"has_uterus": null}` successfully sets `has_uterus` to null in DB
- [ ] "Prefer not to say" selection in settings page persists after refresh
- [ ] Test: `test_update_settings_when_has_uterus_null_then_clears_value`

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Traced "prefer not to say" flow from frontend → PATCH body → model → repository
- Confirmed value is silently dropped by None check
