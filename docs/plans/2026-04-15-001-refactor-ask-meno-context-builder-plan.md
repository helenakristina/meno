---
title: "refactor: Extract ContextBuilder and Remove Fallback Citation Pipeline"
type: refactor
status: active
date: 2026-04-15
---

# refactor: Extract ContextBuilder and Remove Fallback Citation Pipeline

## Overview

Structural refactor of the Ask Meno backend in two logical commits. No behavior changes, no new features. Goal: reduce responsibility sprawl in `AskMenoService` and `PromptService`, remove confirmed-dead fallback code, and establish a clean seam for conversation history.

**Origin PRD:** `docs/planning/prds/2026-04-16_REFACTOR_MENO.md`

---

## Problem Statement

Three distinct problems addressed in one PR:

1. **`PromptService.build_system_prompt()` is doing too much.** `prompts.py:27–135` mixes static layer composition with formatting for age, sources, cycle context, medication block, and symptom summary — all inline. These are distinct concerns.

2. **The fallback citation pipeline is dead code.** `ask_meno.py:297–324` runs `sanitize_and_renumber()` → `verify_citations()` → `extract()` when JSON parsing fails. Stress tests confirmed it never triggers in production. It implies structural unreliability the evidence doesn't support.

3. **Conversation history needs a clean home.** The follow-on PRD will add `conversation_history` context to prompts. This refactor creates the right injection point before that work begins.

---

## Proposed Solution

### Commit 1: Extract `ContextBuilder`

**New file:** `backend/app/utils/context_builder.py`

Move all dynamic Layer 5 formatting out of `build_system_prompt()` into a static `ContextBuilder.build()` method. `PromptService` becomes a thin five-layer compositor.

**What moves to `ContextBuilder`:**

- `age_str` formatting (line 51)
- `source_lines` / `sources_block` — RAG chunk formatting (lines 53–64)
- `cycle_lines` / `cycle_block` — conditional cycle context (lines 66–82)
- `med_block` — `MedicationContext` formatting with sanitization (lines 84–114)
- `layer_4` assembly (lines 116–125)
- `_sanitize_prompt_field()` static method (line 22) — **deleted**; `ContextBuilder` calls `sanitize_prompt_input(value, max_length=N)` directly

**`ContextBuilder.build()` signature (from PRD):**

```python
class ContextBuilder:
    @staticmethod
    def build(
        journey_stage: str,
        age: int | None,
        symptom_summary: str,
        chunks: list[dict],
        cycle_context: dict | None = None,
        has_uterus: bool | None = None,
        medication_context: MedicationContext | None = None,
    ) -> str:
        ...
```

**`PromptService.build_system_prompt()` after refactor:**

```python
@staticmethod
def build_system_prompt(...) -> str:
    context_block = ContextBuilder.build(
        journey_stage, age, symptom_summary, chunks,
        cycle_context, has_uterus, medication_context
    )
    return "\n\n".join([
        LAYER_1_IDENTITY,
        LAYER_2_VOICE,
        LAYER_3_SOURCE_RULES,
        LAYER_4_SCOPE,
        context_block,
    ])
```

**Future hook:** `ContextBuilder.build()` gains `conversation_history: list[dict] | None = None` in the conversation history PRD. The parameter is added there, not here.

### Commit 2: Remove Fallback Citation Pipeline

**Delete from `AskMenoService.ask()` (`ask_meno.py:297–324`):**

```python
# Remove the entire except block:
except Exception as exc:
    logger.warning("Failed to parse structured LLM response ... falling back to free-text pipeline")
    sanitize_result = self.citation_service.sanitize_and_renumber(response_text, len(chunks))
    response_text = sanitize_result.text
    response_text, stripped = self.citation_service.verify_citations(response_text, chunks)
    if stripped:
        logger.warning("Fallback pipeline stripped %d citations ...")
    citations = self.citation_service.extract(response_text, chunks)
    logger.info("Fallback pipeline extracted %d citation(s) ...")
```

The `try` block stays without the `except` — structured response failures will surface as real errors.

**Delete from `CitationService` (`citations.py`):**

- `verify_citations()` — lines 200–277
- `sanitize_and_renumber()` — lines 279–378
- `CitationExtractResult` NamedTuple — lines 17–20 (only used by `sanitize_and_renumber`)

Confirm: `extract()` is called on the primary path and is **not** being deleted.

---

## Technical Considerations

### ⚠️ Critical Risk: `_claim_source_overlap` Audit

The institutional learning at `docs/solutions/security-issues/ask-meno-v2-review-learnings.md` documents a prior incident where removing the fallback pipeline silently dropped citation overlap verification (`_claim_source_overlap`). **Before deleting the fallback, verify `_claim_source_overlap` runs on the primary path inside `render_structured_response()`.**

- If it runs on the primary path → safe to delete.
- If it only runs in the fallback → it must be moved to the primary path before the fallback is removed.

This is a pre-condition gate for Commit 2.

### Test Impact

**Delete entirely (methods no longer exist):**

- `test_citations.py` — `TestSanitizeAndRenumber` class (lines 46–219, 14 tests) + 3 integration tests in `TestIntegration` (lines 360–416) that call `sanitize_and_renumber` as part of the pipeline
- `test_ask_meno_service.py` — `test_v1_json_format_triggers_fallback` test (line ~584)
- `test_ask_meno_service.py` — fixture lines 102–105 that set up `mock_citation_service.sanitize_and_renumber` and `mock_citation_service.verify_citations`

**Update (import/call path changes):**

- `test_prompts.py` — `TestSanitizePromptField` class (lines 128–167, 6 tests) — **delete**; `sanitize_prompt_input` already has its own coverage

**New tests to write (TDD: write before implementing):**

- `tests/utils/test_context_builder.py` — byte-for-byte output parity test (acceptance criterion)
- Route-level test for `ask()` primary path with a **correctly-shaped JSON mock** (not plain text). This is required per the institutional learning — after removing the fallback, tests must exercise the real primary code path.

### Architecture Fit

`ContextBuilder` in `backend/app/utils/context_builder.py` fits naturally alongside:

- `prompt_formatting.py` — symptom/medication formatting for appointment prompts (simpler model)
- `sanitize.py` — `sanitize_prompt_input()` for user input
- `logging.py` — `hash_user_id()` etc.

**Note on overlap:** `prompt_formatting.py` has `format_medications_for_prompt()` for a simpler `MedicationResponse` list. `ContextBuilder` handles the richer `MedicationContext` model (with `current_medications` + `recent_changes`). These are distinct — do not merge.

### No Cross-Domain Dependencies

`ContextBuilder` takes data objects as inputs and returns a string. No repository or service injection required — it's a pure formatting utility, fits cleanly in `utils/` per the `ValueError`-in-utils rule documented in `docs/solutions/logic-errors/backend-phase4-type-safety-and-interface-cleanup.md`.

### Sanitization Must Be Preserved

Per `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md`:

- `_sanitize_prompt_field(value, max_len)` is a strict subset of `sanitize_prompt_input(text, max_length)` — same newline stripping and truncation, plus `sanitize_prompt_input` additionally strips XML tags and role injection markers.
- **Delete `_sanitize_prompt_field` entirely.** `ContextBuilder` calls `sanitize_prompt_input(value, max_length=N)` with the appropriate per-field length (100 for name, 50 for dose/method/frequency/end_date, 500 for symptom_summary). This is a net improvement — medication fields gain XML tag and role marker stripping.
- The 6 `TestSanitizePromptField` tests can be deleted — `sanitize_prompt_input` already has its own test coverage in `tests/utils/test_sanitize.py`.

---

## System-Wide Impact

### Interaction Graph

`AskMenoService.ask()` → `PromptService.build_system_prompt()` → `ContextBuilder.build()` → formatted string.

After the refactor, the only change to the call chain is the insertion of `ContextBuilder.build()` between `build_system_prompt` and the inline formatting logic it replaced. No other callers of `build_system_prompt` exist.

### Error Propagation

After Commit 2, a JSON parse failure or Pydantic validation error in `ask()` raises an unhandled exception that propagates to the route's global exception handler → 500. This is correct behavior for a pipeline with confirmed structured response reliability. Add a log statement at the raise site so failures are observable.

### State Lifecycle Risks

No state involved — `ContextBuilder` is a pure function (no DB, no side effects). Deleting the fallback removes a silent degradation path; errors surface immediately. No partial-state risk.

### API Surface Parity

`build_system_prompt()` signature is unchanged — same parameters, same return type. Callers in `ask_meno.py` need no changes. The refactor is entirely internal to `PromptService`.

### Integration Test Scenarios

1. `build_system_prompt()` with all optional params (cycle, medications) → output identical to pre-refactor (parity test)
2. `build_system_prompt()` with `cycle_context=None`, `medication_context=None` → no blocks appear in output
3. `ask()` with valid structured JSON response → primary path executes, citations returned
4. `ask()` with malformed JSON response → exception propagates (not silently swallowed)
5. `_sanitize_prompt_field()` on a string with newlines and length > max → correct truncation and newline stripping via `ContextBuilder`

---

## Acceptance Criteria

- [ ] `PromptService.build_system_prompt()` contains no inline string formatting logic (only calls `ContextBuilder.build()` and joins five constants)
- [ ] `ContextBuilder.build()` is in `backend/app/utils/context_builder.py`
- [ ] Byte-for-byte output parity test in `tests/utils/test_context_builder.py` passes
- [ ] `CitationService` no longer contains `sanitize_and_renumber()`, `verify_citations()`, or `CitationExtractResult`
- [ ] Fallback `except` block is gone from `ask()` in `ask_meno.py`
- [ ] `_claim_source_overlap` confirmed present on the primary path before Commit 2 merges
- [ ] All remaining Ask Meno tests pass
- [ ] `TestSanitizePromptField` tests deleted — `_sanitize_prompt_field` is gone; `ContextBuilder` calls `sanitize_prompt_input` directly, which has its own coverage
- [ ] New route-level test for `ask()` primary path uses correctly-shaped JSON mock
- [ ] No changes to prompt content, LLM parameters, or API behavior

---

## Implementation Order (TDD)

### Commit 1: ContextBuilder Extraction

1. **Write failing tests first** in `tests/utils/test_context_builder.py`:
   - Output parity test (compare against current `build_system_prompt` output)
   - `_sanitize_prompt_field` unit tests (copy/adapt from `TestSanitizePromptField`)
   - Conditional block tests (no cycle, no meds, both present)
2. Run tests → confirm they fail
3. Create `backend/app/utils/context_builder.py` — move formatting logic
4. Update `backend/app/services/prompts.py` — thin compositor
5. Update `backend/tests/services/test_prompts.py` — `TestSanitizePromptField` calls `ContextBuilder._sanitize_prompt_field`
6. Run all tests → confirm green

### Commit 2: Remove Fallback Pipeline

1. **Audit `_claim_source_overlap`** — read `citations.py:render_structured_response()`, confirm it runs on the primary path. This is a gate — do not proceed until confirmed.
2. **Write new route-level primary-path test** with correctly-shaped JSON mock → confirm it fails if fallback is required
3. Remove fallback `except` block from `ask_meno.py`
4. Delete `sanitize_and_renumber()`, `verify_citations()`, `CitationExtractResult` from `citations.py`
5. Delete `TestSanitizeAndRenumber` class and `TestIntegration` fallback tests from `test_citations.py`
6. Delete `test_v1_json_format_triggers_fallback` and fixture mock lines from `test_ask_meno_service.py`
7. Run all tests → confirm green

---

## Files Modified

### New

- `backend/app/utils/context_builder.py`
- `backend/tests/utils/test_context_builder.py`

### Modified

- `backend/app/services/prompts.py` — thin compositor; remove `_sanitize_prompt_field` (deleted — subsumed by `sanitize_prompt_input`)
- `backend/app/services/ask_meno.py` — remove fallback `except` block (lines 297–324)
- `backend/app/services/citations.py` — delete `sanitize_and_renumber` (279–378), `verify_citations` (200–277), `CitationExtractResult` (17–20)
- `backend/tests/services/test_prompts.py` — update `TestSanitizePromptField` import/call path
- `backend/tests/services/test_citations.py` — delete `TestSanitizeAndRenumber` + affected `TestIntegration` tests
- `backend/tests/services/test_ask_meno_service.py` — delete fallback test + fixture mock lines; add primary-path route test

### Unchanged

- All routes, models, repositories
- Frontend
- Prompt content (LAYER_1–LAYER_4 constants)
- `CitationService.extract()` (primary path, not deleted)
- `CitationService.render_structured_response()`

---

## Dependencies & Risks

| Risk                                                                | Likelihood                            | Mitigation                                      |
| ------------------------------------------------------------------- | ------------------------------------- | ----------------------------------------------- |
| `_claim_source_overlap` only on fallback path                       | Medium (prior incident)               | Hard gate: audit before Commit 2                |
| Other callers of `sanitize_and_renumber` or `verify_citations`      | Low (research confirmed none)         | Grep before deleting                            |
| Parity regression in `ContextBuilder` output                        | Low                                   | Parity test is an acceptance criterion          |
| Test suite imports `PromptService._sanitize_prompt_field` elsewhere | Low (6 tests found, all in one class) | Delete — `sanitize_prompt_input` already tested |

---

## Sources & References

### Internal References

- **Origin PRD:** `docs/planning/prds/2026-04-16_REFACTOR_MENO.md`
- **Critical institutional learning (fallback/overlap risk):** `docs/solutions/security-issues/ask-meno-v2-review-learnings.md`
- **Utils placement rule:** `docs/solutions/logic-errors/backend-phase4-type-safety-and-interface-cleanup.md`
- **Sanitization pattern:** `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md`
- **PromptService:** `backend/app/services/prompts.py:27–135`
- **AskMenoService.ask():** `backend/app/services/ask_meno.py:83–354` (fallback at 297–324)
- **CitationService:** `backend/app/services/citations.py` (verify_citations: 200–277, sanitize_and_renumber: 279–378)
- **Existing utils:** `backend/app/utils/prompt_formatting.py`, `backend/app/utils/sanitize.py`
- **Test files:** `backend/tests/services/test_prompts.py:128–167`, `backend/tests/services/test_citations.py:46–219`, `backend/tests/services/test_ask_meno_service.py`
