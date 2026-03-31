---
title: "Refactor: Appointment Prep — Scenarios, Prompts, and PDFs"
type: refactor
status: active
date: 2026-03-30
---

# Refactor: Appointment Prep — Scenarios, Prompts, and PDFs

## Overview

Four-phase refactor of the appointment prep pipeline. The feature works correctly but the implementation has four compounding code quality problems: hardcoded scenario logic, scattered prompts, duplicated formatting, and plain-text PDFs. Each phase is a standalone PR. Phases 1 and 3 are pure refactors with no behavior change. Phase 2 changes prompt content (voice). Phase 4 changes PDF output (visual).

**Delivery order:** Phase 3 → Phase 1 → Phase 2 → Phase 4 (dependencies run smallest-to-largest).

---

## Problem Statement

1. **Hardcoded scenarios** — `_select_scenarios()` in `appointment.py` (lines 649–849) is a 200-line if/elif chain returning `list[str]`. `_get_scenario_category()` (lines 851–908) reverse-classifies those same strings. Adding a scenario requires touching application logic. The two methods are tightly coupled through string content.

2. **Scattered prompts** — Six LLM prompts are inline f-strings split across `appointment.py` (narrative) and `llm.py` (symptom summary, provider questions, scenario suggestions, and two PDF prompts). Inconsistent voice: some clinical, some warm, no structure.

3. **Duplicated stat formatting** — Frequency stats, co-occurrence stats, and medication list formatting appear near-identically in three places. `generate_provider_questions()` has a slightly different co-occurrence format (no percentage, "and" instead of "+"), which complicates extraction but does not justify duplication.

4. **Plain appointment PDFs** — The export PDF uses structured reportlab with tables, color, headers, and branding. Appointment prep PDFs go through `markdown_to_pdf()` — a generic renderer that produces unstyled output. The appointment prep documents (given to patients and providers) should look as professional as the export.

---

## Proposed Solution

### Phase 3: DRY Up Stat Formatting (PR 1 — smallest, unblocks Phase 2)

**New file:** `backend/app/utils/prompt_formatting.py`

Pure functions only — no HTTP context, no DB access, raises `ValueError` (not `HTTPException`):

```python
# backend/app/utils/prompt_formatting.py

def format_frequency_stats_for_prompt(
    frequency_stats: list[SymptomFrequency],
    max_items: int = 10,
) -> str:
    """Format frequency stats as prompt-ready text."""
    lines = [
        f"- {s.symptom_name} ({s.category}): logged {s.count} time(s)"
        for s in frequency_stats[:max_items]
    ]
    return "\n".join(lines) if lines else "No symptom data available."


def format_cooccurrence_stats_for_prompt(
    cooccurrence_stats: list[SymptomPair],
    max_items: int = 5,
    verbose: bool = True,
) -> str:
    """Format co-occurrence stats as prompt-ready text.

    Args:
        verbose: If True (default), includes percentage rate. Set False for
                 generate_provider_questions() which uses the shorter format.
    """
    if not cooccurrence_stats:
        return "No notable co-occurrence patterns."
    lines = []
    for p in cooccurrence_stats[:max_items]:
        if verbose:
            lines.append(
                f"- {p.symptom1_name} + {p.symptom2_name}: "
                f"co-occurred {p.cooccurrence_count} time(s) "
                f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
            )
        else:
            lines.append(
                f"- {p.symptom1_name} and {p.symptom2_name} "
                f"co-occurred {p.cooccurrence_count} time(s)"
            )
    return "\n".join(lines)


def format_medications_for_prompt(medications: list) -> str:
    """Format current medications as prompt-ready text. Returns empty string if none."""
    if not medications:
        return ""
    lines = [
        f"- {m.medication_name} {m.dose} ({m.delivery_method})"
        + (f", started {m.start_date}" if m.start_date else "")
        for m in medications
    ]
    return "\n\nCurrent MHT medications:\n" + "\n".join(lines)
```

**Update three call sites:**

- `appointment.py._build_narrative_prompts()` (lines 607–633) — replace inline formatting with `format_frequency_stats_for_prompt()`, `format_cooccurrence_stats_for_prompt(verbose=True)`, `format_medications_for_prompt()`
- `llm.py.generate_symptom_summary()` (lines 99–117) — same
- `llm.py.generate_provider_questions()` (lines 185–199) — use `format_cooccurrence_stats_for_prompt(verbose=False)`

**Critical:** Preserve exact sentinel strings. `test_llm.py` asserts `"No symptom data available" in call_args.kwargs["user_prompt"]`. The utility functions must return these exact strings.

---

### Phase 1: Extract Scenarios to JSON Config (PR 2)

**New file:** `backend/config/scenarios.json`

Follows the established pattern of `backend/config/starter_prompts.json`. Each scenario entry includes `"title"` and `"category"` directly, eliminating the need for `_get_scenario_category()`:

```json
{
  "symptom_scenarios": {
    "cognitive": {
      "keywords": ["brain fog", "cognitive", "concentration", "memory", "focus"],
      "dismissals": [
        {"title": "Brain fog is just normal aging", "category": "normalization"},
        {"title": "That's probably anxiety, not hormones", "category": "psychology"},
        {"title": "You should see a neurologist, not a gynecologist", "category": "specialist-referral"},
        {"title": "Cognitive symptoms don't respond to hormone therapy", "category": "dismissal"},
        {"title": "Cognitive decline at your stage is expected", "category": "normalization"}
      ]
    },
    "vasomotor": { ... },
    "sleep": { ... },
    "anxiety": { ... },
    "genitourinary": { ... },
    "mood": { ... },
    "pain": { ... },
    "fatigue": { ... },
    "skin_hair": { ... }
  },
  "goal_scenarios": {
    "explore_hrt": [ ... ],
    "optimize_current_treatment": [ ... ],
    "assess_status": [ ... ]
  },
  "universal_scenarios": [ ... ]
}
```

**Note:** `_select_scenarios()` currently returns `list[str]` (titles only). After this change it will return `list[dict]` with `title` and `category` keys — callers that use these results must be updated. Verify all call sites of `_select_scenarios()` in `appointment.py` before implementing.

**Replace `_select_scenarios()`** with a config-driven method that loads from JSON, deduplicates by title, and caps at 7 results:

```python
def _load_scenario_config(self) -> dict:
    """Load scenario config from JSON. Follows same lazy-load pattern as AskMenoService._prompt_config."""
    if not hasattr(self, "_scenario_config") or self._scenario_config is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "scenarios.json"
        with config_path.open() as f:
            self._scenario_config = json.load(f)
    return self._scenario_config

def _select_scenarios(self, context: AppointmentContext, journey_stage: str) -> list[dict]:
    """Select 5-7 dismissal scenarios from config based on appointment context."""
    config = self._load_scenario_config()
    scenarios: list[dict] = []

    if context.goal.value == "urgent_symptom" and context.urgent_symptom:
        symptom = context.urgent_symptom.lower()
        for group in config["symptom_scenarios"].values():
            if any(kw in symptom for kw in group["keywords"]):
                scenarios.extend(group["dismissals"])
                break

    if not scenarios:
        goal_scenarios = config["goal_scenarios"].get(context.goal.value, [])
        scenarios.extend(goal_scenarios)

    scenarios.extend(config["universal_scenarios"])

    seen: set[str] = set()
    unique: list[dict] = []
    for s in scenarios:
        if s["title"] not in seen:
            unique.append(s)
            seen.add(s["title"])
    return unique[:7]
```

**Eliminate `_get_scenario_category()`** entirely — category comes from the `"category"` key on each dict.

---

### Phase 2: Centralize Appointment Prompts (PR 3)

**New file:** `backend/app/llm/appointment_prompts.py`

Follows `system_prompts.py` pattern: module-level constants for static content, builder functions for dynamic content. Named one builder per LLM call:

```python
# backend/app/llm/appointment_prompts.py

# ── Static system prompt constants ──────────────────────────────────────────

NARRATIVE_SYSTEM = """You are a clinical data summarizer..."""  # extracted from appointment.py:577

SYMPTOM_SUMMARY_SYSTEM = """You are a clinical data summarizer..."""  # extracted from llm.py:73

PROVIDER_QUESTIONS_SYSTEM = """..."""  # extracted from llm.py:162

SCENARIO_SUGGESTIONS_SYSTEM = """You are coaching a woman preparing for a difficult medical appointment.

Voice:
- Sound like a confident friend coaching her, not a script from a medical textbook
- "I hear you, but..." not "I appreciate that stress can play a role, but research shows..."
- Ground responses in the user's own tracked data when available
- Be specific to the dismissal — don't give generic responses
- 2-3 sentences max — this needs to feel natural in a real conversation"""

PROVIDER_SUMMARY_SYSTEM = """..."""  # extracted from llm.py:390

CHEATSHEET_SYSTEM = """..."""  # extracted from llm.py:390 (shared system prompt, split)


# ── Builder functions for dynamic prompts ───────────────────────────────────

def build_narrative_user_prompt(
    appt_type_str: str,
    goal_str: str,
    age_str: str,
    days_back: int,
    start_date: str,
    end_date: str,
    freq_text: str,
    coocc_text: str,
    med_section: str,
) -> str:
    """Assemble the narrative user prompt. Extracted from appointment.py._build_narrative_prompts()."""
    ...

def build_symptom_summary_user_prompt(...) -> str: ...
def build_provider_questions_user_prompt(...) -> str: ...
def build_scenario_suggestions_user_prompt(...) -> str: ...
def build_provider_summary_user_prompt(...) -> str: ...
def build_cheatsheet_user_prompt(...) -> str: ...
```

**Fix LLM call inconsistency:** `appointment.py` calls `.provider.chat_completion()` directly (line 216) for the narrative, bypassing `LLMService`. Add `generate_narrative()` to `LLMService` and update `appointment.py` to call it via the service layer. This ensures future guards (retry, rate limiting, token caps) apply universally.

**Prompt layer separation rule (from learnings):** JSON format instructions and behavioral guardrails must live in separate layers — never combined in one prompt string.

**Input sanitization (from learnings):** All user-supplied strings entering a system prompt must go through `_sanitize_prompt_field()` (strip newlines, truncate). Medication names and other user-generated content can contain prompt injection text — DB content is not a sanitized source.

---

### Phase 4: Structured Appointment PDFs (PR 4 — depends on Phase 2)

**New Pydantic models** in `backend/app/models/appointment.py`:

```python
from pydantic import BaseModel, ConfigDict

class ProviderSummaryResponse(BaseModel):
    """Structured LLM response for provider summary PDF content."""
    model_config = ConfigDict(extra="forbid")

    opening: str
    symptom_picture: str
    key_patterns: str | None = None
    concerns: list[str]
    closing: str


class SymptomByImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    frequency: str   # e.g. "16 episodes in 60 days"
    impact: str      # e.g. "Disrupting sleep and work performance"
    what_to_say: str


class QuestionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    questions: list[str]


class CheatsheetResponse(BaseModel):
    """Structured LLM response for personal cheat sheet PDF content."""
    model_config = ConfigDict(extra="forbid")

    opening_statement: str
    symptoms_by_impact: list[SymptomByImpact]
    concerns: list[str]
    questions: list[QuestionGroup]
```

**`extra="forbid"` is required** on every model parsing LLM JSON (from learnings). Schema regressions fail loudly instead of silently.

**New `PdfService` methods** in `backend/app/services/pdf.py`, following `build_export_pdf()` pattern (lines 179–435):

- `build_provider_summary_pdf(summary: ProviderSummaryResponse, frequency_stats, cooccurrence_pairs, concerns, appointment_context) -> bytes`
- `build_cheatsheet_pdf(cheatsheet: CheatsheetResponse, scenarios: list[dict], concerns, appointment_context) -> bytes`

Both methods: accept structured data, build a `story: list` of reportlab flowables, call `doc.build(story)`, return `bytes`.

**PDF color palette** (defined as module-level constants, matching Meno design system):

```python
_PRIMARY      = HexColor("#14b892")   # Teal — headers, accents
_NEUTRAL_DARK = HexColor("#292524")   # Headings
_NEUTRAL_MED  = HexColor("#57534e")   # Body text
_NEUTRAL_LIGHT = HexColor("#a8a29e")  # Muted text, disclaimers
_ACCENT       = HexColor("#fb923c")   # Coral — highlights, scenario cards
_BORDER       = HexColor("#e7e5e4")   # Borders, dividers
_HEADER_BG    = HexColor("#f0fdf9")   # Light teal — table headers
_ALT_ROW      = HexColor("#fafaf9")   # Alternating rows
```

**`build_provider_summary_pdf()` structure:**

- Meno header with teal branding
- Patient context section (age, journey stage, appointment type, goal)
- Narrative summary (`ProviderSummaryResponse.opening`, `symptom_picture`, `key_patterns`, `closing`)
- Symptom frequency table (same style as export PDF)
- Co-occurrence patterns table (if available)
- Prioritized concerns list
- Disclaimer footer

**`build_cheatsheet_pdf()` structure:**

- Warm header ("Your Appointment Prep")
- Opening statement
- Symptoms by impact (from `CheatsheetResponse.symptoms_by_impact`)
- Key concerns
- Questions to ask (grouped by `QuestionGroup.topic`)
- "If Things Go Sideways" section — scenario cards from Phase 1 `list[dict]` (dismissal + response pairs, coral accent, visually distinct)
- "What to Bring" checklist — **static list, not LLM-generated**

**"If Things Go Sideways" and "What to Bring" are NOT generated by the LLM.** They come from scenario data already collected in Step 4 of the appointment flow and a hardcoded checklist. The PDF service assembles them directly.

**No user names anywhere** — not in JSON, not in prompts, not in PDFs. The provider knows who their patient is.

**Updated flow in `appointment.py.generate_pdf()`:**

1. Fetch all appointment data (existing)
2. Call LLM for structured JSON (new prompts from `appointment_prompts.py`), returning `ProviderSummaryResponse` and `CheatsheetResponse`
3. Parse JSON with `model_validate()` (new Pydantic models, `extra="forbid"`)
4. Pass typed models + scenario data + frequency stats to `build_provider_summary_pdf()` and `build_cheatsheet_pdf()`
5. Upload and return URLs (existing)

**Eliminate `generate_pdf_content()`** from `llm.py` entirely — the two large branching user prompts move to `appointment_prompts.py` as two separate builder functions.

---

## Technical Considerations

### Architecture Impacts

- `_select_scenarios()` return type changes from `list[str]` → `list[dict]`. All callers in `appointment.py` must be updated — verify before implementing. Tests that assert on scenario content strings must be updated to use `s["title"]`.
- Adding `generate_narrative()` to `LLMService` adds a new method to the service layer. `dependencies.py` wiring does not change.
- Phase 4 replaces the `markdown_to_pdf()` path in `generate_pdf()`. The `markdown_to_pdf()` method itself is not deleted (it may be used elsewhere); only the call site in `generate_pdf()` changes.
- Medication data in appointment context must flow through `MedicationServiceBase`, not `MedicationRepository` directly (documented pitfall — see learnings). Verify this is already the case before Phase 4.

### Performance

- `scenarios.json` is loaded once and cached on `self._scenario_config` (lazy-load pattern, matching `AskMenoService._prompt_config`). No per-request file I/O.
- Phase 4 adds two additional LLM calls (provider summary + cheat sheet structured JSON). These replace two existing LLM calls for markdown PDF content. Net LLM call count is unchanged.

### Security & Privacy (Critical for health app)

- **Input sanitization:** All user-supplied strings entering LLM prompts (medication names, symptom names, urgent symptom text) must pass through `_sanitize_prompt_field()` — strip newlines, truncate. The database is not a sanitized source.
- **PII-safe logging:** Log structure and metadata only. Never log symptom names, medication names, appointment goals, or user-generated text. Use `hash_user_id()`, `safe_len()`, `safe_keys()` from `app.utils.logging`.
- **No user names in PDFs** — ever. Not in prompts, not in JSON responses, not in the PDF content.

### Error Handling

- Phase 4 LLM JSON parsing: if `model_validate()` raises `ValidationError` (malformed LLM response), catch and either retry with a simplified prompt or fall back gracefully. Define the fallback behavior explicitly — do not silently return an empty PDF.
- Phase 1 JSON loading: if `scenarios.json` is missing or malformed, raise a descriptive error at startup/first load, not silently return empty scenarios.

---

## System-Wide Impact

### Interaction Graph

`generate_pdf()` in `appointment.py` → `LLMService.generate_pdf_content()` (Phase 4: eliminated) → `PdfService.markdown_to_pdf()` (Phase 4: replaced by `build_provider_summary_pdf()` + `build_cheatsheet_pdf()`)

After Phase 4: `generate_pdf()` → `LLMService.generate_provider_summary()` + `LLMService.generate_cheatsheet()` (new) → `PdfService.build_provider_summary_pdf()` + `build_cheatsheet_pdf()` (new)

`_select_scenarios()` is called by `generate_scenarios()` in `appointment.py` (Step 4 of the flow). Its output (after Phase 1) is `list[dict]` with `title` and `category`. These dicts flow into the Step 4 response and are later passed to `generate_pdf()` (Step 5). Verify this data path is intact after Phase 1.

### Error Propagation

- Phase 1: JSON load failure → `FileNotFoundError` / `json.JSONDecodeError` → should be caught at service init and raise a `ConfigurationError` (or equivalent domain exception), not surface as a 500
- Phase 4: LLM returns malformed JSON → `json.JSONDecodeError` or `ValidationError` → catch in `appointment.py`, log error metadata (not content), raise `ServiceError` → route returns 502

### State Lifecycle Risks

- Phase 1 changes `_select_scenarios()` return type from `list[str]` to `list[dict]`. If any downstream code accesses scenarios by index as strings (e.g. `scenarios[i]` treated as a string), it will silently fail or raise `TypeError`. Audit all usages before merging.
- Phase 4 adds no new persistent state. PDF bytes are generated, uploaded to storage, and URLs stored as before.

### API Surface Parity

No API surface changes in any phase. All four phases are internal refactors — request/response schemas for routes do not change.

### Integration Test Scenarios

1. **Phase 1 regression:** Call the full appointment Step 4 flow end-to-end with `goal=urgent_symptom` and `urgent_symptom="brain fog"` — verify scenarios contain cognitive-category entries, not empty
2. **Phase 1 regression:** Call Step 4 with `goal=explore_hrt` — verify HRT-related scenarios are returned
3. **Phase 4 PDF bytes:** Call `generate_pdf()` end-to-end with mocked LLM returning valid `ProviderSummaryResponse` + `CheatsheetResponse` JSON — verify both returned URLs are non-empty and the PDF bytes start with `%PDF`
4. **Phase 4 malformed LLM response:** Mock LLM returning invalid JSON for provider summary — verify graceful error, not unhandled exception
5. **Cross-phase:** After all four phases, run the full 5-step appointment prep flow and verify the PDF output contains the "If Things Go Sideways" section populated from the scenarios selected in Step 4

---

## Acceptance Criteria

### Phase 3: Stat Formatting

- [x] `backend/app/utils/prompt_formatting.py` exists with `format_frequency_stats_for_prompt`, `format_cooccurrence_stats_for_prompt`, `format_medications_for_prompt`
- [x] `format_cooccurrence_stats_for_prompt(verbose=False)` produces the "and" format (no percentage) used by `generate_provider_questions()`
- [x] All three call sites in `appointment.py` and `llm.py` use the shared formatters
- [x] No formatting logic duplication remains
- [x] Sentinel strings ("No symptom data available.", "No notable co-occurrence patterns.") preserved exactly
- [x] All existing tests pass without modification
- [x] New unit tests for all three utility functions

### Phase 1: Scenarios

- [x] `backend/config/scenarios.json` exists with all 10 symptom groups, 3 goal groups, and universal scenarios
- [x] `_select_scenarios()` reads from JSON, returns `list[dict]` with `title` and `category`
- [x] `_get_scenario_category()` is deleted
- [x] All callers of `_select_scenarios()` updated for new return type
- [x] Scenario selection logic produces equivalent results for all goal types
- [x] Adding a new scenario requires only a JSON edit
- [x] `_scenario_config` loaded in `__init__` (fails at instantiation, not query time)
- [x] Config load failure raises a descriptive domain error, not a silent empty list
- [x] All existing tests pass; tests updated for `list[dict]` return type
- [x] New tests for config loading and scenario selection routing

### Phase 2: Prompts

- [ ] `backend/app/llm/appointment_prompts.py` exists with all 6 system prompt constants and 6 builder functions
- [ ] No hardcoded prompt strings remain in `appointment.py` or `llm.py`
- [ ] `LLMService.generate_narrative()` method added; `appointment.py` uses it (no more `.provider` direct calls)
- [ ] Patient-facing prompts (scenario suggestions, cheat sheet) include Meno voice layer
- [ ] Provider-facing prompts (narrative, provider summary) remain clinical
- [ ] Scenario response suggestions pass the "confident friend" test, not medical textbook
- [ ] User-supplied strings sanitized via `_sanitize_prompt_field()` before entering prompts
- [ ] All existing tests pass; prompt-content assertions updated if prompt wording changed

### Phase 4: PDFs

- [ ] `ProviderSummaryResponse`, `SymptomByImpact`, `QuestionGroup`, `CheatsheetResponse` models added to `appointment.py` with `extra="forbid"`
- [ ] `PdfService.build_provider_summary_pdf()` and `build_cheatsheet_pdf()` added
- [ ] `generate_pdf_content()` deleted from `llm.py`
- [ ] Provider summary PDF: structured reportlab with Meno branding, frequency table, co-occurrence table, concerns
- [ ] Cheat sheet PDF: includes "If Things Go Sideways" (from scenario data) and static "What to Bring" checklist
- [ ] PDFs use Meno design system colors
- [ ] No user names appear anywhere in PDF output
- [ ] LLM JSON parse failure triggers graceful error, not unhandled exception
- [ ] PDF bytes begin with `%PDF` (smoke test)
- [ ] Manual comparison: appointment PDFs now visually match the quality of the export PDF

---

## Testing Strategy

### Phase 3 (pure refactor)

- Existing tests pass without modification — this is the first quality gate
- Add `tests/utils/test_prompt_formatting.py` with unit tests for each formatter:
  - `format_frequency_stats_for_prompt` with data, empty list, max_items
  - `format_cooccurrence_stats_for_prompt` verbose=True and verbose=False
  - `format_medications_for_prompt` with meds and empty list

### Phase 1 (pure refactor)

- Existing tests pass — verify `TestSelectScenarios` (lines 382–459 in `test_appointment_service.py`) still works after updating for `list[dict]` return type
- Add tests for: `_load_scenario_config()` returns valid dict, `_select_scenarios()` routes correctly for each goal type, missing JSON file raises descriptive error
- **Do not delete `TestSelectScenarios`** — update it

### Phase 2 (prompt content changes)

- Update test mocks that assert on exact prompt strings
- Manual quality check: generate scenario suggestions with the new voice layer and verify they read naturally
- Verify `generate_narrative()` in `LLMService` is exercised by existing or new tests

### Phase 4 (new behavior — PDF structure)

- Add `test_pdf_service.py` tests for `build_provider_summary_pdf()` and `build_cheatsheet_pdf()`:
  - Happy path: returns bytes starting with `%PDF`
  - All required sections are present (smoke test via content inspection)
- Update `test_appointment_service.py` mocks for `generate_pdf()`: mocks must return valid JSON matching `ProviderSummaryResponse` and `CheatsheetResponse` schemas (not plain text)
- Manual comparison of old vs new PDF output

---

## Dependencies & Prerequisites

- Phase 3 has no prerequisites — implement first
- Phase 1 requires Phase 3 (calls shared formatters in prompt construction)
- Phase 2 requires Phase 3 (builder functions use shared formatters)
- Phase 4 requires Phase 2 (new LLM methods use centralized prompts)
- All phases: verify medication data flows through `MedicationServiceBase`, not `MedicationRepository` directly (documented pitfall from `docs/solutions/architecture-issues/feature-flag-bypass-via-direct-repo-injection.md`)

---

## Files Affected

| File                                                 | Changes                                                                                                                                                                                                                         |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/config/scenarios.json`                      | **NEW** — full scenario config (Phase 1)                                                                                                                                                                                        |
| `backend/app/utils/prompt_formatting.py`             | **NEW** — shared stat formatters (Phase 3)                                                                                                                                                                                      |
| `backend/app/llm/appointment_prompts.py`             | **NEW** — all appointment LLM prompts (Phase 2)                                                                                                                                                                                 |
| `backend/app/services/appointment.py`                | Refactor: remove `_select_scenarios` if/elif chain, remove `_get_scenario_category`, remove inline prompt f-strings, add `_load_scenario_config`, use prompt layer + shared formatters, call `llm_service.generate_narrative()` |
| `backend/app/services/llm.py`                        | Refactor: remove inline prompts from 5 methods, use `appointment_prompts.py` builders, add `generate_narrative()`, eliminate `generate_pdf_content()` (Phase 4)                                                                 |
| `backend/app/services/pdf.py`                        | **NEW methods**: `build_provider_summary_pdf`, `build_cheatsheet_pdf`. Add Meno color constants if not already present.                                                                                                         |
| `backend/app/models/appointment.py`                  | **NEW models**: `ProviderSummaryResponse`, `SymptomByImpact`, `QuestionGroup`, `CheatsheetResponse`                                                                                                                             |
| `backend/tests/utils/test_prompt_formatting.py`      | **NEW** — unit tests for formatters (Phase 3)                                                                                                                                                                                   |
| `backend/tests/services/test_appointment_service.py` | Update: `TestSelectScenarios` for `list[dict]` return type, Phase 4 mock returns valid JSON                                                                                                                                     |
| `backend/tests/services/test_llm.py`                 | Update: prompt-content assertions after Phase 2                                                                                                                                                                                 |
| `backend/tests/services/test_pdf_service.py`         | Update/Add: tests for new PDF methods (Phase 4)                                                                                                                                                                                 |

---

## Risk Analysis

| Risk                                                                             | Likelihood     | Impact | Mitigation                                                               |
| -------------------------------------------------------------------------------- | -------------- | ------ | ------------------------------------------------------------------------ |
| `_select_scenarios()` return type change breaks callers silently                 | Medium         | High   | Audit all call sites before Phase 1 merge; update type hints             |
| LLM returns malformed JSON for Phase 4 (PDFs)                                    | Medium         | High   | Validate with `extra="forbid"` Pydantic models; define explicit fallback |
| Prompt voice change in Phase 2 degrades clinical tone of provider-facing prompts | Low            | Medium | Keep provider/patient prompts clearly separated; manual review           |
| Medication feature flag bypass in appointment service                            | Low (existing) | High   | Verify before Phase 4; documented in `docs/solutions/`                   |
| Test mocks for Phase 4 still return plain text (not JSON)                        | High           | Medium | Update all `generate_pdf_content` mocks to return valid structured JSON  |

---

## Sources & References

### Internal References

- Architecture patterns: `docs/dev/backend/V2CODE_EXAMPLES.md`
- Prompt layer rules: `docs/solutions/security-issues/ask-meno-v2-review-learnings.md`
- Pydantic patterns & DRY utils: `docs/solutions/logic-errors/backend-phase4-type-safety-and-interface-cleanup.md`
- Feature flag bypass pitfall: `docs/solutions/architecture-issues/feature-flag-bypass-via-direct-repo-injection.md`
- Frontend/backend type mismatch: `docs/solutions/logic-errors/frontend-backend-response-type-mismatch.md`
- Existing scenario logic: `backend/app/services/appointment.py:649–908`
- Existing prompt locations: `backend/app/services/llm.py:73–625`
- Export PDF pattern: `backend/app/services/pdf.py:179–435`
- Existing prompt module: `backend/app/llm/system_prompts.py`
- Config precedent: `backend/config/starter_prompts.json`
- Appointment models: `backend/app/models/appointment.py`
- Appointment tests: `backend/tests/services/test_appointment_service.py:382–459`
