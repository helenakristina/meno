# PRD: Ask Meno Service Refactor

## Status
Draft

## Overview
Structural refactor of the Ask Meno backend — no behavior changes, no new features. The goal is to reduce responsibility sprawl in `AskMenoService` and `PromptService`, remove confirmed-dead fallback code, and establish clean seams for the upcoming conversation history feature.

---

## Motivation

Three problems are being addressed:

**`PromptService.build_system_prompt()` is doing too much.** It assembles the static prompt layers *and* formats all dynamic user context (cycle data, medication block, sources block) inline. As context complexity grows, this method grows with it. Context formatting and layer composition are distinct responsibilities and should be separated.

**The fallback citation pipeline is dead code.** The fallback in `ask()` — which runs `sanitize_and_renumber()` → `verify_citations()` → `extract()` on raw text when JSON parsing fails — has been confirmed never to trigger in production. Three stress-test scenarios (jailbreak, dosing redirect, creative writing framing) all returned valid structured responses. The fallback implies unreliability in the structured pipeline that the evidence does not support, and it obscures the primary code path.

**The upcoming conversation history feature needs a clean home.** Rather than bolting turn history onto already-heavy methods, this refactor establishes `ContextBuilder` as the right place for that logic to live.

---

## Scope

### In scope
- Extract `ContextBuilder` from `PromptService`
- Slim down `PromptService.build_system_prompt()` to layer composition only
- Remove the fallback citation pipeline block from `AskMenoService.ask()`
- Delete orphaned `CitationService` methods: `sanitize_and_renumber()` and `verify_citations()`

### Out of scope
- Conversation history / within-session context (separate PRD)
- Any changes to prompt content or LLM behavior
- Frontend changes
- Test changes beyond updating for removed methods

---

## Design

### New: `ContextBuilder`

**Location:** `backend/app/utils/context_builder.py`

Owns all formatting of the dynamic Layer 5 context block. Takes raw data objects as inputs, returns a formatted string ready for prompt assembly.

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

Responsible for:
- Journey stage / age / symptom summary block
- Cycle context block (conditional)
- Medication block (conditional, including current and recently stopped)
- Sources block (numbered chunks)
- `_sanitize_prompt_field()` utility (moves here from `PromptService`)

### Revised: `PromptService`

`build_system_prompt()` becomes a thin compositor — it calls `ContextBuilder.build()` and joins the five layers. No formatting logic remains inline.

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

### Revised: `AskMenoService.ask()`

Remove the `except` block that runs the fallback citation pipeline. The try/except around `json.loads()` and structured response rendering either succeeds or raises — no silent fallback.

```python
# Before
try:
    structured = StructuredLLMResponse(**raw_response)
    response_text, citations = self.citation_service.render_structured_response(...)
except Exception as exc:
    logger.warning(...)
    # ... fallback pipeline ...

# After
structured = StructuredLLMResponse(**raw_response)
response_text, citations = self.citation_service.render_structured_response(...)
```

If JSON parsing fails, it should raise and surface as an error — not silently degrade into an unstructured response. This is the correct behavior for a pipeline with confirmed structured response reliability.

### Revised: `CitationService`

Delete:
- `sanitize_and_renumber()`
- `verify_citations()`

Both are only called from the fallback pipeline. Confirm no other callers before deletion.

---

## Commit Plan

Two commits within a single PR:

**Commit 1: Extract ContextBuilder from PromptService**
- New file: `context_builder.py`
- Updated: `prompts.py` (thin compositor)
- Updated: any imports that reference `PromptService._sanitize_prompt_field` directly (unlikely but check)

**Commit 2: Remove fallback citation pipeline**
- Updated: `ask_meno.py` (remove fallback block)
- Updated: `citation_service.py` (delete two methods)
- Updated: any tests covering deleted methods

---

## Acceptance Criteria

- `PromptService.build_system_prompt()` contains no inline string formatting logic
- `ContextBuilder.build()` produces byte-for-byte identical output to the previous inline implementation for the same inputs — verify with a unit test
- `CitationService` no longer contains `sanitize_and_renumber()` or `verify_citations()`
- The fallback `except` block is gone from `ask()`
- All existing Ask Meno tests pass without modification (beyond deleted method tests)
- No changes to prompt content, LLM parameters, or API behavior

---

## Future Hook

`ContextBuilder.build()` is the intended injection point for conversation history in the follow-on PRD. The signature will gain a `conversation_history: list[dict] | None = None` parameter in that work.