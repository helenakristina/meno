---
title: "Rename 'Symptom Summary' → 'My Health Picture' and Remove closing Field"
type: refactor
status: completed
date: 2026-04-08
---

# Rename "Symptom Summary" → "My Health Picture" and Remove `closing` Field

## Overview

Two tightly coupled cleanup changes to the appointment prep flow:

1. **Rename**: "Symptom Summary" → "My Health Picture" across the frontend UI and PDF.
2. **Remove**: The `closing` field from `ProviderSummaryResponse` (and all LLM prompt/PDF code that produces or consumes it), removing the corresponding "Next Steps" section from the provider summary PDF.

All changes are string replacements and a field removal with no database impact. Single commit — a partial commit would leave the UI and PDF out of sync.

## Problem Statement / Motivation

The Step 2 narrative section is called "Symptom Summary" in the UI and PDF, but it also covers medication context, making the name inaccurate. "My Health Picture" better reflects the full scope and uses consistent first-person voice.

The "Next Steps" section in the provider summary PDF (`content.closing`) is redundant with the "Patient's Prioritized Concerns" list that precedes it. Removing it shortens the document and increases provider read-through.

## Proposed Solution

Update 5 backend files, 2 frontend files, and corresponding tests in a single atomic commit. No database changes required — `ProviderSummaryResponse` is generated fresh at Step 5 and never persisted.

## Pre-Change Verification (Do First)

Before making any changes, run these greps and review results:

```bash
# Verify all closing hits in app/ — confirm no unexpected references
grep -rn "closing" backend/app/

# Verify all symptom summary hits — confirm scope
grep -rni "symptom summary" .
```

**Expected `closing` hits in `backend/app/`** (all in-scope):

- `app/models/appointment.py:483` — field definition
- `app/llm/appointment_prompts.py:328` — JSON spec
- `app/services/llm.py:404` — Returns docstring
- `app/services/pdf.py:484` — docstring
- `app/services/pdf.py:581` — `content.closing` usage

**Out-of-scope `closing` hits** (do not touch):

- `app/llm/system_prompts.py:74` — refers to citation index closing remarks
- `app/models/chat.py:16` — refers to citation index closing remarks

If any unexpected hits appear outside these files, stop and report before proceeding.

## Technical Considerations

### `extra="ignore"` vs PRD's stated `extra="forbid"`

Research found that `ProviderSummaryResponse` currently uses `extra="ignore"`, not `extra="forbid"` as the PRD risk note states. This means after `closing` is removed from the model:

- If the LLM still returns a `closing` field in its JSON, it will be **silently ignored** (not a hard-fail)
- This is still correct behavior — the PDF won't render a closing section regardless
- Do NOT change the `extra=` setting; leave it as-is per project standards

### Frontend TypeScript Interface Audit

Before marking complete, audit `frontend/src/lib/types/` for any TypeScript interface that mirrors `ProviderSummaryResponse`. If `closing` appears in a frontend type, remove it. A missing field causes a silent runtime `undefined` (not a compile-time error due to `as any` casts in the API client).

### Test Fixture Cleanup Is Mandatory

`extra="ignore"` means tests passing `closing` in fixture data won't immediately fail, but stale fixtures mask issues. All test references to `closing` must be removed in the same commit.

## Changes Required

### Backend — `app/models/appointment.py`

**Location:** `ProviderSummaryResponse` class, line 483

Remove:

```python
closing: str
```

After removal, the model should have exactly two fields: `opening: str` and `key_patterns: str = ""`.

---

### Backend — `app/llm/appointment_prompts.py`

**Location:** `build_provider_summary_user_prompt`, line 325–329

Update from three-field JSON spec to two-field:

```python
# Before
f"Return ONLY a valid JSON object with exactly these three fields:\n"
f'{{"opening": "2-3 sentence intro: who, why here, urgent concern if any", '
f'"key_patterns": "2-3 sentences on co-occurring patterns if present, else empty string", '
f'"closing": "1-2 sentences on what the patient is seeking from this appointment"}}\n\n'
f"No markdown. No explanation. No extra fields. Valid JSON only."

# After
f"Return ONLY a valid JSON object with exactly these two fields:\n"
f'{{"opening": "2-3 sentence intro: who, why here, urgent concern if any", '
f'"key_patterns": "2-3 sentences on co-occurring patterns if present, else empty string"}}\n\n'
f"No markdown. No explanation. No extra fields. Valid JSON only."
```

---

### Backend — `app/services/llm.py`

**Location:** `generate_provider_summary_content` docstring, Returns line ~404

Update:

```python
# Before
ProviderSummaryResponse with opening, key_patterns, closing.

# After
ProviderSummaryResponse with opening and key_patterns.
```

---

### Backend — `app/services/pdf.py`

Three changes:

**5a. Remove Next Steps section** (lines 579–581)

Remove:

```python
# --- Closing ---
story.append(Paragraph("Next Steps", heading_style))
story.append(Paragraph(content.closing, body_style))
```

**5b. Rename "Symptom Summary" heading** (line 533)

Change:

```python
# --- Symptom Summary (verbatim from user's narrative) ---
story.append(Paragraph("Symptom Summary", heading_style))
```

to:

```python
# --- My Health Picture (verbatim from user's narrative) ---
story.append(Paragraph("My Health Picture", heading_style))
```

**5c. Update docstring** (line 484–485)

Change:

```python
content: Structured LLM response with opening, key_patterns, and closing.
narrative: User's narrative text, inserted verbatim as "Symptom Summary".
```

to:

```python
content: Structured LLM response with opening and key_patterns.
narrative: User's narrative text, inserted verbatim as "My Health Picture".
```

---

### Frontend — `Step2Narrative.svelte`

**File:** `frontend/src/routes/(app)/appointment-prep/Step2Narrative.svelte`

⚠️ **PRD discrepancy:** The PRD says `"Loading your symptom summary"` but the actual code says `"Generating your symptom summary…"`. Use the actual strings found in the file.

Change (line 74):

```svelte
Generating your symptom summary…
```

to:

```svelte
Generating your health picture…
```

Change (line 101, `<label>` text):

```svelte
Your symptom summary
```

to:

```svelte
Your health picture
```

---

### Frontend — `appointment.ts` (STEP_TITLES)

**File:** `frontend/src/lib/types/appointment.ts`, line 114

Change:

```typescript
2: 'Your symptom summary',
```

to:

```typescript
2: 'Your health picture',
```

---

### Frontend — `Step1Context.svelte` (Additional — not in PRD)

**File:** `frontend/src/routes/(app)/appointment-prep/Step1Context.svelte`, line 171

Research found an additional rename target not listed in the PRD — the "Next" button label on Step 1:

Change:

```svelte
Next: Generate symptom summary
```

to:

```svelte
Next: Generate health picture
```

---

## Test Updates Required

All test references to `closing` must be removed in the same commit.

### `backend/tests/models/test_appointment_pdf_models.py`

- Remove `"closing"` key from all fixture dicts
- Remove `"closing": "C"` from all `ProviderSummaryResponse(...)` constructor calls
- Delete `test_missing_closing_raises_validation_error` test entirely

### `backend/tests/llm/test_appointment_prompts.py`

- Update or delete `test_schema_has_opening_key_patterns_closing` (currently asserts `"closing" in result`)
- Replace with `test_schema_has_opening_and_key_patterns` asserting only two fields

### `backend/tests/services/test_llm.py`

- Line 504: Remove `"closing": "Seeks treatment discussion."` from `_VALID_JSON` fixture
- Line 565: Remove `"closing": "C"` from inline test JSON
- Update any assertion that checks for three fields to check for two

### `backend/tests/services/test_pdf_service.py`

- Update `_provider_content()` factory (line 229) — remove `closing="Patient seeks discussion of treatment options."`
- Remove inline `closing="Seeking discussion."` override (line 342)
- Update or remove any test that asserts PDF bytes contain `"Next Steps"` content

### `backend/tests/services/test_appointment_service.py`

- Line 103: Remove `closing="Patient seeks treatment options."` from `ProviderSummaryResponse` mock

---

## Frontend Type Audit

Grep `frontend/src/` for `closing` to catch any TypeScript interface mirroring `ProviderSummaryResponse`:

```bash
grep -rn "closing" frontend/src/
```

If 'closing` appears in a TypeScript type that corresponds to ProviderSummaryResponse, remove it from that type and any component that accesses it. If `closing` appears in any other context, stop and report it rather than removing it.

---

## Acceptance Criteria

- [ ] `ProviderSummaryResponse` has exactly two fields: `opening` and `key_patterns`
- [ ] `build_provider_summary_pdf` does not reference `content.closing` anywhere
- [ ] `build_provider_summary_user_prompt` requests exactly two JSON fields
- [ ] `generate_provider_summary_content` docstring no longer mentions `closing`
- [ ] `Step2Narrative.svelte` uses "health picture" (not "symptom summary") in all strings
- [ ] `Step1Context.svelte` "Next" button says "Generate health picture"
- [ ] `STEP_TITLES[2]` is `'Your health picture'`
- [ ] PDF heading is "My Health Picture" (not "Symptom Summary")
- [ ] PDF no longer has a "Next Steps" section
- [ ] All test fixtures have `closing` removed
- [ ] `test_missing_closing_raises_validation_error` deleted
- [ ] All backend tests pass (`uv run pytest -v -m "not integration"`)
- [ ] Frontend builds clean (`npm run build`)

## Post-Change Verification

```bash
# 1. No symptom summary in appointment prep files
grep -rni "symptom summary" frontend/src/routes/\(app\)/appointment-prep/ backend/app/services/pdf.py

# 2. No closing in in-scope backend files
grep -n "closing" backend/app/models/appointment.py backend/app/llm/appointment_prompts.py backend/app/services/llm.py backend/app/services/pdf.py

# 3. No closing in test files
grep -rn "closing" backend/tests/

# 4. Run tests
cd backend && uv run pytest -v -m "not integration"

# 5. Frontend build
cd frontend && npm run build
```

Expected: All greps return no hits. All tests pass. Build succeeds.

## Out of Scope

- Voice or content changes to any prompt
- Changes to `CheatsheetResponse` or the cheatsheet PDF
- Changes to `build_export_pdf` or the health export flow (`"Symptom Pattern Summary"` heading in that function is intentionally unchanged)
- Database migrations

## Dependencies & Risks

- **No DB migration needed.** `ProviderSummaryResponse` is generated fresh at Step 5 and never stored.
- **`extra="ignore"` behavior:** After removing `closing`, if the LLM returns the field, it is silently discarded. This is acceptable — the PDF will simply not render the section.
- **Single commit required.** Partial commits leave UI and PDF out of sync (e.g., Step 2 says "health picture" but PDF still says "Symptom Summary").

## Sources & References

- PRD: `docs/planning/prds/PRD_APPT_PREP_RENAME`
- Backend models: `backend/app/models/appointment.py:479`
- PDF service: `backend/app/services/pdf.py:484`
- LLM prompts: `backend/app/llm/appointment_prompts.py:325`
- Svelte component: `frontend/src/routes/(app)/appointment-prep/Step2Narrative.svelte:74`
- STEP_TITLES: `frontend/src/lib/types/appointment.ts:114`
- Step1 button: `frontend/src/routes/(app)/appointment-prep/Step1Context.svelte:171`
- Learnings: `docs/solutions/security-issues/remove-user-id-from-api-responses.md` (field removal pattern)
- Learnings: `docs/solutions/logic-errors/frontend-backend-response-type-mismatch.md` (frontend type audit after backend model change)
