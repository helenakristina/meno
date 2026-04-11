---

title: "feat: Appointment Prep Flow Refactor — Phase 5 (PRD2)"
type: feat
status: completed
date: 2026-04-01
origin: docs/planning/prds/PRD_APPOINTMENT_PREP_REFACTOR_2.md

---

# feat: Appointment Prep Flow Refactor — Phase 5

## Overview

Close the gap between the current appointment prep flow and the gold-standard document produced during dogfooding. Six areas of work across backend, frontend, and LLM prompt layers — each with a clear before/after.

**Branch:** `refactor/appointment-prep-phase5-enhancements` → PR to `refactor/appointment-prep-phase3-stat-formatting`

**Source:** [PRD_APPOINTMENT_PREP_REFACTOR_2.md](docs/planning/prds/PRD_APPOINTMENT_PREP_REFACTOR_2.md)

---

## Problem Statement

The appointment prep flow has four compounding problems:

1. **Narrative is rewritten, not used verbatim.** The user edits a generated narrative in Step 2; that text is passed to an LLM that summarizes it — the user's words never appear in the output. User edits are functionally discarded.
2. **Input is too thin.** The wizard captures appointment type, goal, dismissed flag, and optional urgent symptom. It doesn't capture what the user has tried, what they specifically want, or clinical history that directly shapes provider summary content.
3. **Concerns are flat strings.** Users can prioritize concerns but can't add context to individual items. The provider has no idea _why_ joint pain is #1 on the list.
4. **Scenarios are ungrounded.** `generate_scenario_suggestions` calls OpenAI with instructions to cite evidence but provides none, or worse, provides hallucinated sources. Sources field is always empty; the prior "fix" was to suppress citations entirely, which removed evidential value.

---

## Proposed Solution

Six discrete, sequentially independent changes — most can be implemented and tested in isolation.

### Area 1 — Step 0: Intro Page (Frontend Only)

**What:** New page at `/appointment-prep` (before the wizard begins) surfacing both document names, wizard duration, data sources, and a "Start your prep" CTA.

**Frontend changes:**

- New route: `frontend/src/routes/(app)/appointment-prep/+page.svelte`
- Nav bar "Appt Prep" link routes here instead of directly to wizard Step 1
- Content follows PRD Section 1 verbatim (tone: Meno's voice, not marketing)

**No backend changes required.**

### Area 2 — Step 2: Narrative Verbatim in Provider Summary (Backend + Frontend)

#### 2a. UX Fix (Frontend)

Add explicit framing above the edit box in Step 2:

> "This summary goes directly to your provider's document, word for word. Read it carefully and edit anything that doesn't sound right or doesn't reflect your experience. This is the most important thing you'll do in this process."

Add secondary note below textarea:

> "Your edits are saved automatically. What you see here is what your provider will read."

**File:** `frontend/src/routes/(app)/appointment-prep/step2/+page.svelte`

#### 2b. Architectural Fix (Backend)

**Current:** `build_provider_summary_user_prompt` requests `symptom_picture` from the LLM. The narrative is passed as context and rewritten.

**New:**

- Remove `symptom_picture` from `ProviderSummaryResponse` (Pydantic model in `backend/app/models/appointment.py`)
- Remove `symptom_picture` from `PROVIDER_SUMMARY_SYSTEM` JSON schema
- Remove narrative context from `build_provider_summary_user_prompt` — prompt now generates only `opening`, `key_patterns`, `closing`
- In `build_provider_summary_pdf()`: insert the saved narrative verbatim between the `opening` and `key_patterns` sections, labelled "Symptom Summary"

**Files:**

- `backend/app/models/appointment.py` — `ProviderSummaryResponse` remove `symptom_picture: str`
- `backend/app/llm/appointment_prompts.py` — update `PROVIDER_SUMMARY_SYSTEM`, `build_provider_summary_user_prompt`
- `backend/app/services/pdf.py` — update `build_provider_summary_pdf()` to insert narrative verbatim

**Tests to update:**

- `backend/tests/llm/test_appointment_prompts.py` — update provider summary prompt tests
- `backend/tests/models/test_appointment_pdf_models.py` — update `ProviderSummaryResponse` fixture
- `backend/tests/services/test_pdf_service.py` — update provider summary PDF builder tests

### Area 3 — Step 3: Concern Comments (Backend + Frontend)

#### 3a. Data Model Change

Concerns change from `string[]` → `Concern[]`:

```python
# backend/app/models/appointment.py
class Concern(BaseModel):
    text: str
    comment: str | None = None
```

**Backend changes:**

- Add `Concern` model to `backend/app/models/appointment.py`
- Update `SaveConcernsRequest` to use `list[Concern]`
- Update `AppointmentRepository.save_concerns()` and `get_concerns()` — serialise as JSONB array
- Update `build_provider_summary_user_prompt` and `build_cheatsheet_user_prompt` to format concerns as `"Joint pain; can't get through a workday without it"` when comment is present
- Update PDF renderers to display comment beneath concern label in secondary style

**Files:**

- `backend/app/models/appointment.py`
- `backend/app/repositories/appointment_repository.py`
- `backend/app/llm/appointment_prompts.py`
- `backend/app/services/pdf.py`

**TypeScript interface update** (must happen immediately with backend change):

```typescript
// frontend/src/lib/types/appointment.ts (or wherever AppointmentPrepState is defined)
interface Concern {
  text: string;
  comment?: string;
}
// concerns: string[] → concerns: Concern[]
```

**Frontend changes:**

- Each concern card in Step 3 gets an optional inline comment field
- Placeholder: "What specifically do you want your provider to know about this? (optional)"
- Character limit: 200 chars (enforced at UI)
- Field reveals on focus/tap (not always visible)
- `sanitize_prompt_input(comment, max_length=200)` applied server-side

#### 3b. Copy Update (Frontend only)

Old: "Drag to reorder, or use the arrows. Your top concern will be listed first in your materials."
New: "Put what matters most first. Providers often only get to the first few topics raised, lead with what you need most from this appointment."

**File:** `frontend/src/routes/(app)/appointment-prep/step3/+page.svelte`

### Area 4 — Step 3.5: Qualitative Context Step (Backend + Frontend)

**New wizard step** between Step 3 and Step 4.

#### Backend: Data Model

Add 4 fields to `AppointmentContext`:

```python
# backend/app/models/appointment.py — AppointmentContext
what_have_you_tried: str | None = None
specific_ask: str | None = None
history_clotting_risk: str | None = None   # "yes" | "no" | "not_sure"
history_breast_cancer: str | None = None   # "yes" | "no" | "not_sure"
```

Also update `CreateAppointmentContextRequest` / `UpdateAppointmentContextRequest` accordingly (or create a dedicated `SaveQualitativeContextRequest`).

**Sanitization:** All three free-text inputs use `sanitize_prompt_input` with their character limits:

- `what_have_you_tried`: `max_length=500`
- `specific_ask`: `max_length=300`
- Contraindication flags: enum-validated ("yes" | "no" | "not_sure"), no sanitization needed

**Repository:** Update `save_context()` / `get_context()` to persist these 4 fields.

**Prompt changes:**

- `build_narrative_user_prompt`: receives `what_have_you_tried`, `specific_ask`
- `build_provider_summary_user_prompt`: receives all 4 fields; if `history_clotting_risk == "yes"` or `history_breast_cancer == "yes"`, include in opening context
- `build_cheatsheet_user_prompt`: receives `specific_ask` to drive "Your Key Ask" section

**Files:**

- `backend/app/models/appointment.py`
- `backend/app/repositories/appointment_repository.py`
- `backend/app/llm/appointment_prompts.py`
- `backend/app/api/routes/appointment.py` (add route for new step if needed, or extend existing save_context)

**Frontend:**

- New step component: `frontend/src/routes/(app)/appointment-prep/step3-5/+page.svelte`
- Step title: "A little more about you"
- Step subtitle: "This helps us write materials that sound like you, not a statistics report."
- Three fields per PRD Section 5 (content verbatim)
- Inline note for Yes selection on contraindication questions: "We'll make sure your materials note this. Discuss with your provider how it affects your options."
- Character counters at 400/500 and 250/300 respectively
- Wizard state: add 4 new fields to `AppointmentPrepState`

### Area 5 — Step 4: RAG-Grounded Scenarios (Backend)

**Current:** `generate_scenario_suggestions` calls OpenAI directly; `sources` field always empty; citation suppression in place.

**New:** Each scenario generated using the RAG pipeline before calling LLM.

#### Implementation

In `AppointmentService._generate_scenario_suggestions` (or equivalent):

```python
# For each selected scenario:
# 1. Use scenario title as retrieval query
chunks = await rag_retriever(scenario_title, top_k=5, min_similarity=0.25)
# 2. Pass chunks to build_scenario_suggestions_user_prompt
# 3. Populate sources from chunk metadata
```

`rag_retriever` is already injected into `AppointmentService.__init__` as a `Callable` (see memory note: inject as Callable, don't import directly). If not currently injected, add it following the same pattern as `AskMenoService`.

**Prompt changes:**

- `SCENARIO_SUGGESTIONS_SYSTEM`: restructure to follow one-source-per-claim model (see `LAYER_3_SOURCE_RULES` in Ask Meno prompts for reference found at `backend/app/llm/system_prompts.py`)
- Remove "CRITICAL: Do NOT include URLs or citations" suppression
- Add "use only the provided source documents" instruction
- `sources` field: `[{"title": str, "excerpt": str}]` populated from RAG

**Output schema** (already in Pydantic, confirm `extra="forbid"` per learnings):

```python
class ScenarioSuggestion(BaseModel, extra="forbid"):
    scenario_title: str
    suggestion: str
    sources: list[dict]  # [{"title": str, "excerpt": str}]
```

**Fallback:** If RAG returns no chunks, generate without grounding; `sources` stays empty. No fabricated citations.

**Frontend (Step 4):**

- Display source citations beneath each scenario card in small secondary style
- "Based on: [title]" — only shown when `sources` is non-empty

**Files:**

- `backend/app/services/appointment.py`
- `backend/app/llm/appointment_prompts.py`
- `backend/app/api/routes/appointment.py` (if `rag_retriever` injection needs to be added)
- `backend/app/api/dependencies.py` (if DI wiring needs update)
- `frontend/src/routes/(app)/appointment-prep/step4/+page.svelte`

**Tests:**

- `backend/tests/services/test_appointment_service.py` — mock `rag_retriever`, test with/without chunks, test fallback
- `backend/tests/llm/test_appointment_prompts.py` — update scenario prompt tests

### Area 6 — Step 5: Copy Change (Frontend Only)

Add subtitle beneath checkmark on the results screen:

> "Your Provider Summary is ready to email ahead or hand to your provider. Your Personal Cheat Sheet is yours to carry in."

**File:** `frontend/src/routes/(app)/appointment-prep/step5/+page.svelte`

---

## Technical Considerations

### Sanitization

`sanitize_prompt_input(text, max_length)` in `backend/app/utils/sanitize.py` already accepts `max_length` parameter (per this sprint's refactor). All new free-text fields use it with their specific limits. Do not create additional sanitization functions.

### Model Evolution

`AppointmentContext` already has 4 existing fields. New fields are all `Optional` with `None` default — backward-compatible with existing saved contexts. No migration required for the context JSONB column (Supabase handles sparse JSON natively).

`ProviderSummaryResponse` loses `symptom_picture`. Any code that reads this field (tests, PDF builder) must be updated in the same PR — no backwards compat needed since this is internal.

### RAG Injection Pattern

Per institutional learnings: inject `rag_retriever` as a `Callable` in `AppointmentService.__init__`, wired via `dependencies.py`. Do not import `retrieve_relevant_chunks` directly in the service module.

### Concern Serialization

Concerns stored as JSONB array: `[{"text": "...", "comment": "..."}]`. `get_concerns()` returns `list[Concern]`. The repository should handle both old format (`string[]`) and new format gracefully if there are any existing saved concerns — or accept that existing concerns in dev are throwaway.

### PDF Section Order (Provider Summary)

Current order: opening → symptom_picture (LLM) → key_patterns → closing → concerns table → frequency table

New order: opening → [narrative verbatim, labelled "Symptom Summary"] → key_patterns → closing → concerns table → frequency table

---

## System-Wide Impact

### Interaction Graph

```
Step 3.5 save → appointment_repository.save_context() → JSONB update
Step 4 generate → rag_retriever(scenario_title) → retrieve_relevant_chunks() → pgvector query
Step 5 generate provider summary → build_provider_summary_user_prompt() [no symptom_picture] → LLM → ProviderSummaryResponse
Step 5 build PDF → build_provider_summary_pdf() → inserts narrative verbatim from DB
```

### Error Propagation

- RAG retrieval failure in Step 4 → fall back to no-source generation (not an error, logged at INFO)
- `ProviderSummaryResponse` parse failure → `DatabaseError` (existing pattern, unchanged)
- Narrative verbatim: if narrative not found in DB when building PDF → `DatabaseError` (must be explicit, not a silent empty section)

### State Lifecycle Risks

- Removing `symptom_picture` from `ProviderSummaryResponse`: any in-flight PDF generation that fails mid-refactor could produce an empty section. Non-issue in dev; gate with feature flag if shipping to prod users.
- New `AppointmentContext` fields are nullable — partial saves (user abandons Step 3.5) leave these null, which is fine; prompts handle `None` as "not provided".

### API Surface Parity

Step 3.5 is a new step — it needs its own save endpoint or must be handled by the existing `PUT /api/appointment-prep/{id}/context` if the model accepts the new fields. Prefer extending the existing endpoint (add fields to the model) over adding a new route. Confirm narrative edit endpoint gap from todo #010 is addressed (PUT endpoint for narrative editing).

### Integration Test Scenarios

1. Full wizard happy path with all Step 3.5 fields filled → PDF contains narrative verbatim, concern comments, correct source citations
2. Step 3.5 skipped (all fields null) → PDF still builds, prompts handle None gracefully, no crashes
3. RAG returns 0 chunks for a scenario → `sources: []`, no source badge in UI, no fabricated citations
4. Concern with 200-char comment → truncated at sanitize layer, stored, displayed in PDF without overflow
5. User with `history_clotting_risk: "yes"` → provider summary opening mentions it; cheatsheet does not

---

## Acceptance Criteria

### Functional

- [ ] Step 0 intro page renders before wizard Step 1; nav link routes correctly
- [ ] Step 2 edit box shows verbatim framing text above and auto-save note below
- [ ] Provider Summary PDF "Symptom Summary" section contains user's narrative exactly as edited
- [ ] `ProviderSummaryResponse` no longer has `symptom_picture` field; LLM prompt no longer requests it
- [ ] Each concern card in Step 3 shows optional comment field (reveals on focus)
- [ ] Concern comments appear in both PDFs beneath concern label in secondary style
- [ ] Step 3.5 renders with all 3 fields; inline note shows on Yes selection for either clinical question
- [ ] Step 3.5 data flows into narrative, provider summary, and cheatsheet prompts correctly
- [ ] Scenario suggestions include real RAG sources when available; `sources` is empty (not fabricated) when not
- [ ] Source badges appear in Step 4 UI only for sourced scenarios
- [ ] Step 5 subtitle copy updated

### Non-Functional

- [ ] All new free-text inputs sanitized via `sanitize_prompt_input` with correct `max_length`
- [ ] Character limits enforced at both UI and backend
- [ ] Contraindication fields are enum-validated ("yes" | "no" | "not_sure")
- [ ] `rag_retriever` injected as Callable in AppointmentService (not imported directly)
- [ ] No PII logged (use `safe_len`, `hash_user_id` per LOGGING.md)

### Quality Gates

- [ ] All existing tests continue to pass
- [ ] New tests written before implementation (TDD per CLAUDE.md)
- [ ] Coverage does not decrease from current baseline
- [ ] `ruff check . && ruff format .` passes

---

## Implementation Phases

### Phase A — Data Model & Backend Foundation

Build order: Models → Repository → Sanitization wiring → Tests

1. Add `Concern` model; update `SaveConcernsRequest`, `get_concerns`, `save_concerns`
2. Add 4 new fields to `AppointmentContext`; update `save_context`, `get_context`
3. Remove `symptom_picture` from `ProviderSummaryResponse`
4. Write tests for all model + repository changes (TDD)

### Phase B — LLM Prompt Updates

Build order: Prompt builders → System prompts → Tests

1. Update `build_provider_summary_user_prompt` — remove narrative context, remove `symptom_picture` from schema, add Step 3.5 fields
2. Update `build_narrative_user_prompt` — add `what_have_you_tried`, `specific_ask`
3. Update `build_cheatsheet_user_prompt` — add `specific_ask`, format concerns with comments
4. Update `SCENARIO_SUGGESTIONS_SYSTEM` — restructure for RAG grounding (see PRD Section 6)
5. Write/update tests for all prompt builders (TDD)

### Phase C — Service Layer

Build order: Service methods → RAG injection → PDF builder → Tests

1. Update `AppointmentService.generate_provider_summary_content` — pass new fields to prompt builder
2. Update `AppointmentService.generate_scenario_suggestions` — RAG retrieval before LLM call
3. Update `build_provider_summary_pdf` — insert narrative verbatim, remove `symptom_picture` usage
4. Update `build_cheatsheet_pdf` — render concern comments
5. Write/update tests (TDD)

### Phase D — Frontend

Build order: Types → Step 3 update → Step 3.5 new → Step 0 new → Step 2 UX → Step 4 sources → Step 5 copy

1. Update TypeScript `Concern` interface and `AppointmentPrepState`
2. Update Step 3 concern cards with comment fields + copy update
3. Build Step 3.5 new page
4. Build Step 0 intro page
5. Add verbatim framing to Step 2
6. Add source badges to Step 4
7. Update Step 5 copy

---

## Dependencies & Prerequisites

- `sanitize_prompt_input(text, max_length)` — already complete (this sprint)
- `retrieve_relevant_chunks` — already in production via Ask Meno RAG pipeline
- Existing `AppointmentService` DI wiring in `dependencies.py` — confirm current injection signature before adding `rag_retriever`
- NAMS guideline coverage gap (PRD Open Question 4): check RAG index coverage before shipping Step 4 to production

---

## Open Questions (from PRD)

1. **Contraindication display in PDFs** (unresolved): Should clotting/breast cancer history appear as a flagged item in the Provider Summary or only inform the prose? Clinical sensitivity and liability implications. **Do not implement PDF flagging until resolved.**

2. **NAMS index coverage**: Confirm which scenario types have sufficient RAG coverage before launch. If coverage is thin, the fallback (no sources) is acceptable for MVP.

---

## Sources & References

### Origin

- **PRD:** [docs/planning/prds/PRD_APPOINTMENT_PREP_REFACTOR_2.md](docs/planning/prds/PRD_APPOINTMENT_PREP_REFACTOR_2.md)
  Key decisions carried forward: (1) narrative verbatim in PDF, not rewritten; (2) `ProviderSummaryResponse` loses `symptom_picture`; (3) RAG grounding is the fix for scenarios, not citation suppression

### Internal References

- Sanitize utilities: `backend/app/utils/sanitize.py`
- RAG retriever: `backend/app/rag/retrieval.py` — `retrieve_relevant_chunks(query, top_k, min_similarity)`
- Appointment service: `backend/app/services/appointment.py`
- Appointment prompts: `backend/app/llm/appointment_prompts.py`
- PDF builder: `backend/app/services/pdf.py`
- AppointmentContext model: `backend/app/models/appointment.py`
- Appointment repository: `backend/app/repositories/appointment_repository.py`
- DI wiring: `backend/app/api/dependencies.py`
- AskMenoService (RAG injection pattern reference): `backend/app/services/ask_meno.py`

### Institutional Learnings

- Prompt injection sanitization pattern: `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md`
- RAG injection as Callable: memory — "inject `rag_retriever` as Callable in `__init__`, wired via `dependencies.py`"
- Use `extra="forbid"` on LLM output models
- Use `model_fields_set` for PATCH with optional fields

### Related Work

- Phase 3 refactor: `refactor/appointment-prep-phase3-stat-formatting` (parent branch)
- Phase 4 PDF: commit `b8425ff` — structured ReportLab PDFs
- Todo #010: verify narrative editing endpoint (PUT `/api/appointment-prep/{id}/narrative`)
