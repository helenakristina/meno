---
title: "feat: Ask Meno v2 — Voice-Forward Response Schema"
type: feat
status: active
date: 2026-03-23
---

# feat: Ask Meno v2 — Voice-Forward Response Schema

## Overview

Refactor the Ask Meno RAG pipeline to produce warm, conversational paragraph-style responses instead of clinical bullet-point claims. Migrate from a per-claim citation model (`StructuredClaim → source_indices[]`) to a one-paragraph-one-source model (`ResponseSection → source_index`). This maintains full citation integrity while enabling Meno's voice to actually sound like Meno.

The complete reference implementation is in `docs/planning/ask_meno_v2_schema.py` — the new Pydantic models and all four static prompt layer constants are ready to copy.

## Problem Statement

Ask Meno's current output reads like a medical database, not a conversation:

```
• "MHT is generally well-tolerated with minimal side effects for the majority and has the
  potential to greatly increase quality of life. [1]"
• "Current recommendations endorse the use of MHT in recently menopausal women with
  appropriate indications. [2]"
```

The desired output is:

> "Most women tolerate MHT really well, and for a lot of us it's a game-changer for quality of life. Current guidelines support starting MHT when you're symptomatic and within the window of opportunity — before 60 and within 10 years of menopause."

This is a backend-driven architectural change with a small frontend update. The API contract (`ChatResponse`, `ChatMessage`, `Citation`) is unchanged.

## Proposed Solution

Replace the claim-based model hierarchy with a paragraph-based one. Each response section contains a single paragraph of prose drawn from exactly one source. Update the system prompt to enforce Meno's voice. Update `CitationService.render_structured_response()` to emit paragraphs instead of bullet lists. Minimal changes everywhere else.

## Technical Approach

### Architecture

```
LLM → JSON {sections: [{heading, body, source_index}]} → StructuredLLMResponse
  → CitationService.render_structured_response()
    → paragraph text + deduplicated Citation list
  → ChatResponse (unchanged)
  → Frontend: marked.parse() → <p> tags (no changes needed)
```

The fallback pipeline (`sanitize_and_renumber → verify_citations → extract`) stays intact for non-JSON LLM responses.

### Implementation Phases

#### Phase 1: Models (`backend/app/models/chat.py`)

**Remove:**
- `StructuredClaim` (lines 8–12)
- `StructuredSection` (lines 15–19)
- `StructuredLLMResponse` (lines 22–27) — the old one

**Add** (copy from `docs/planning/ask_meno_v2_schema.py`):

```python
class ResponseSection(BaseModel):
    """A paragraph drawn from exactly ONE source."""
    heading: str | None = None
    body: str = Field(
        description="Conversational paragraph in Meno's voice. Plain text, no markdown."
    )
    source_index: int | None = Field(
        default=None,
        description="1-based index of the single source. null only for closing/disclaimer."
    )


class StructuredLLMResponse(BaseModel):
    """Complete structured response from the LLM."""
    sections: list[ResponseSection] = Field(default_factory=list)
    disclaimer: str | None = None
    insufficient_sources: bool = False
```

**Keep unchanged:** `Citation`, `ChatMessage`, `ChatRequest`, `ChatResponse`, `ConversationSummary`, `ConversationListResponse`, `ConversationMessagesResponse`, `SuggestedPromptsResponse`

#### Phase 2: System Prompts (`backend/app/llm/system_prompts.py`)

Replace the current four layer constants (`LAYER_1`, `LAYER_2`, `LAYER_3`, dynamic LAYER_4) with five constants (copy directly from `docs/planning/ask_meno_v2_schema.py`):

| New constant | Replaces | What it adds |
|---|---|---|
| `LAYER_1_IDENTITY` | `LAYER_1` | Same identity, slightly expanded |
| `LAYER_2_VOICE` | *(new)* | Voice rules, before/after examples, anti-patterns |
| `LAYER_3_SOURCE_RULES` | `LAYER_2` | New JSON schema (`body + source_index` instead of `claims[]`), one-source rule |
| `LAYER_4_SCOPE` | `LAYER_3` | Same guardrails, cleaned up |
| *(dynamic Layer 5)* | `LAYER_4` | User context + RAG chunks — assembled by PromptService, unchanged |

> ⚠️ **Name collision risk:** `LAYER_3` and `LAYER_4` change meaning. `test_chat_guardrails.py` imports the old names directly — these imports will break and must be updated (see Phase 6).

#### Phase 3: Prompt Service (`backend/app/services/prompts.py`)

Update `build_system_prompt()` — imports only, the dynamic assembly logic is unchanged:

```python
# Before
from app.llm.system_prompts import LAYER_1, LAYER_2, LAYER_3

layers = [LAYER_1, LAYER_2, LAYER_3, dynamic_layer_4]

# After
from app.llm.system_prompts import (
    LAYER_1_IDENTITY, LAYER_2_VOICE, LAYER_3_SOURCE_RULES, LAYER_4_SCOPE
)

layers = [LAYER_1_IDENTITY, LAYER_2_VOICE, LAYER_3_SOURCE_RULES, LAYER_4_SCOPE, dynamic_layer_5]
```

The join separator (`"\n\n"`), method signature, and all parameter handling stay the same.

#### Phase 4: Citation Service (`backend/app/services/citations.py`)

This is the most significant code change. Replace the section-loop logic in `render_structured_response()`:

**Old behavior:** For each section → for each claim → bullet point `"- {text} [Source N]"`. Headings rendered as `**{heading}**`.

**New behavior:**

```python
def render_structured_response(
    self, structured: StructuredLLMResponse, chunks: list[dict]
) -> tuple[str, list[Citation]]:
    if structured.insufficient_sources:
        return structured.disclaimer or "I don't have sources to answer that.", []

    paragraphs: list[str] = []
    seen_indices: dict[int, int] = {}   # source_index → display number
    citations: list[Citation] = []

    for section in structured.sections:
        if not section.body.strip():
            continue

        # Build citation marker
        marker = ""
        if section.source_index is not None:
            idx = section.source_index
            if idx not in seen_indices:
                if 1 <= idx <= len(chunks):
                    display_n = len(citations) + 1
                    seen_indices[idx] = display_n
                    chunk = chunks[idx - 1]
                    citations.append(Citation(
                        source_number=display_n,
                        title=chunk.get("title", ""),
                        url=chunk.get("url", ""),
                        section=chunk.get("section", ""),
                    ))
            if idx in seen_indices:
                marker = f" [Source {seen_indices[idx]}]"

        # Render section
        text = section.body.strip() + marker
        if section.heading:
            paragraphs.append(f"{section.heading}\n{text}")
        else:
            paragraphs.append(text)

    rendered = "\n\n".join(paragraphs)
    if not rendered.strip() and structured.disclaimer:
        return structured.disclaimer, []

    if structured.disclaimer:
        rendered += f"\n\n{structured.disclaimer}"

    return rendered, citations
```

The `_claim_source_overlap`, `verify_citations`, `sanitize_and_renumber`, and `extract` methods are unchanged — they serve the fallback pipeline.

> ⚠️ **Current gap:** `render_structured_response()` has **no direct unit tests** in `test_citations.py`. This refactor is the opportunity to add a `TestRenderStructuredResponse` class (see Testing Strategy).

#### Phase 5: Ask Meno Service (`backend/app/services/ask_meno.py`)

Minimal changes only:

```python
# Line ~241: raise max_tokens from 1500 to 2000
max_tokens=2000,

# Line ~244: raise temperature from 0.3 to 0.5
temperature=0.5,
```

The `StructuredLLMResponse` import at line 31 automatically picks up the new model — no other changes needed. The fallback pipeline is unchanged.

#### Phase 6: Fix Broken Imports in Tests

`backend/tests/api/routes/test_chat_guardrails.py` imports old layer names directly. Update:

```python
# Before
from app.llm.system_prompts import LAYER_1, LAYER_2, LAYER_3

# After
from app.llm.system_prompts import (
    LAYER_1_IDENTITY, LAYER_2_VOICE, LAYER_3_SOURCE_RULES, LAYER_4_SCOPE
)
```

Also update any assertions in those tests that reference layer content by the old variable names.

#### Phase 7: Frontend (`frontend/src/routes/(app)/ask/+page.svelte`)

The frontend already handles plain text correctly:
- `marked.parse()` on plain text paragraphs → `<p>` tags automatically
- `[Source N]` → `<sup><a>` superscript replacement is unchanged
- No markdown to strip (the new prompt enforces no markdown from the LLM)

**One change needed:** Headings in the new model are plain text prefixed before the paragraph, not `**bold**` markdown. The current rendering path would display them as plain text next to the paragraph body. If we want headings to look distinct, the heading should be emitted on a separate line with a `###` markdown prefix so `marked` renders it as a heading element.

> Decision needed: plain-text heading (simpler backend, frontend sees a paragraph) or markdown heading prefix (more visual hierarchy). The PRD says "plain text only — the frontend handles formatting." The backend should emit headings as a separate `\n\n###` line and let `marked` render it.

**Recommended approach:** In Phase 4, emit headings as `### {heading}` so `marked` renders them as `<h3>`. This satisfies "frontend controls visual presentation" while keeping the plain-text `body` field clean.

## System-Wide Impact

### Interaction Graph

1. User submits question → `AskMenoService.ask()`
2. `PromptService.build_system_prompt()` → 5-layer prompt (new constants)
3. LLM call → JSON with `sections[{heading, body, source_index}]`
4. `json.loads()` + `StructuredLLMResponse.model_validate()` → new model
5. `CitationService.render_structured_response()` → `(rendered_text, citations[])`
6. `ChatResponse(message=rendered_text, citations=citations)` → frontend
7. `marked.parse(rendered_text)` → HTML → user sees prose paragraphs

### Error & Failure Propagation

- **JSON parse failure** → fallback pipeline in `ask_meno.py` (unchanged, no impact)
- **Pydantic validation failure** (LLM returns v1 schema) → `ValidationError` → fallback pipeline
- **Invalid `source_index`** (out of range) → skip that section's citation marker; body still rendered
- **All sections empty after filtering** → `disclaimer` shown; `citations = []`
- **`insufficient_sources: true`** → short-circuit returns disclaimer immediately

### State Lifecycle Risks

No state mutations. All methods are pure transformations: JSON string → model → (text, citations). No DB writes in this path. No risk of partial failure leaving orphaned state.

### API Surface Parity

The `ChatResponse` model and all `/ask` endpoint response shapes are **unchanged**. Frontend `ChatApiResponse` type is **unchanged**. Only the internal `StructuredLLMResponse` model changes — it is not exposed via the API.

### Integration Test Scenarios

1. **Happy path, 3 sections, 2 unique sources:** Verify deduplicated citations list has 2 items, rendered text has 3 paragraphs with `[Source 1]` / `[Source 2]` / `[Source 1]` markers
2. **`insufficient_sources: true`:** Verify empty `citations[]` and disclaimer text returned immediately
3. **Section with `null` source_index:** Verify no citation marker appended, section body still rendered
4. **LLM returns v1 JSON (regression test):** Verify `ValidationError` triggers fallback pipeline successfully
5. **Full `ask()` with mock LLM:** Verify the rendered text reaches `ChatResponse.message` with correct citation objects

## Acceptance Criteria

### Functional

- [ ] `ResponseSection` and new `StructuredLLMResponse` models exist in `chat.py`; old `StructuredClaim` and `StructuredSection` removed
- [ ] `system_prompts.py` exports `LAYER_1_IDENTITY`, `LAYER_2_VOICE`, `LAYER_3_SOURCE_RULES`, `LAYER_4_SCOPE`; old `LAYER_1/2/3` removed
- [ ] `PromptService.build_system_prompt()` assembles all five layers; voice examples present in assembled prompt
- [ ] `CitationService.render_structured_response()` emits paragraph text, not bullet points
- [ ] Multiple sections referencing the same `source_index` produce one `Citation` object (deduplication)
- [ ] Sections with `heading` render the heading visually distinct from body text
- [ ] Sections with `source_index: null` render body without citation marker
- [ ] `AskMenoService` uses `max_tokens=2000`, `temperature=0.5`
- [ ] `test_chat_guardrails.py` imports updated to new layer constant names

### Non-Functional

- [ ] All existing tests pass with no regressions
- [ ] `render_structured_response()` has direct unit tests (currently has none)
- [ ] The fallback pipeline (non-JSON LLM responses) continues to function correctly
- [ ] No markdown characters (`**`, `##`, `-`) appear in the `body` field of LLM responses (enforced via prompt)

### Quality Gates

- [ ] TDD: each new test has a `CATCHES:` annotation describing the specific bug it prevents
- [ ] `uv run ruff check . && uv run ruff format .` passes
- [ ] `uv run pytest -v -m "not integration"` passes

## Testing Strategy

Follow TDD. Write failing test → watch it fail → implement → pass.

### New: `TestRenderStructuredResponse` in `test_citations.py`

```python
# CATCHES: regression to bullet-point format
def test_renders_paragraph_not_bullets():
    ...  # assert "\n-" not in rendered_text

# CATCHES: duplicate citation objects when same source used twice
def test_deduplicates_citations_same_source():
    ...  # assert len(citations) == 1 when two sections share source_index=1

# CATCHES: heading absent from output when section.heading is None
def test_no_heading_when_null():
    ...  # assert "###" not in rendered_text

# CATCHES: heading rendered above body when present
def test_heading_rendered_above_body():
    ...  # assert "### My Heading\nBody text" in rendered_text

# CATCHES: citation marker appended to wrong section when null source_index mixed in
def test_null_source_index_no_citation_marker():
    ...  # assert "[Source" not in rendered_text for that section

# CATCHES: out-of-range source_index crashes service
def test_invalid_source_index_skipped_gracefully():
    ...  # source_index=99 with 3 chunks → no exception, no marker

# CATCHES: disclaimer omitted when not needed
def test_disclaimer_appended_when_present():
    ...

# CATCHES: insufficient_sources short-circuit bypassed
def test_insufficient_sources_short_circuits():
    ...  # assert rendered == disclaimer_text, citations == []
```

### Update `test_ask_meno_service.py`

Update `LLM_RAW_JSON` constant (line 39) from v1 format to v2:

```python
LLM_RAW_JSON = json.dumps({
    "sections": [
        {"heading": None, "body": "MHT is well-tolerated.", "source_index": 1},
        {"heading": None, "body": "Current guidelines support starting MHT.", "source_index": 2},
    ],
    "disclaimer": None,
    "insufficient_sources": False,
})
```

Add test:

```python
# CATCHES: v1 JSON format silently accepted instead of triggering fallback
def test_v1_json_format_fails_validation_and_triggers_fallback():
    v1_json = json.dumps({"sections": [{"heading": None, "claims": [{"text": "...", "source_indices": [1]}]}]})
    # assert ask() returns fallback response
```

### Update `test_system_prompts.py` (or `test_prompts.py`)

```python
# CATCHES: voice layer missing from assembled prompt
def test_all_five_layers_present():
    prompt = build_system_prompt(...)
    assert "YOUR VOICE:" in prompt
    assert "RESPONSE FORMAT:" in prompt
    assert "IN SCOPE" in prompt

# CATCHES: before/after voice examples removed accidentally
def test_voice_examples_in_prompt():
    prompt = build_system_prompt(...)
    assert "Instead of:" in prompt
```

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| LLM ignores one-source-per-section rule and mixes sources | Medium | Verification checklist in LAYER_3_SOURCE_RULES; fallback pipeline catches malformed JSON |
| LLM returns v1 JSON format after deploy (cached prompt) | Low | v1 validation now fails → fallback gracefully |
| `test_chat_guardrails.py` import breakage | High (certain) | Fix in Phase 6; it's integration-only, not in unit test suite |
| Longer paragraphs exceed `max_tokens` | Low | Raising to 2000 tokens provides headroom |
| Frontend renders heading inline with body (no visual separation) | Medium | Emit `### heading` markdown in Phase 4 so `marked` creates `<h3>` |

## Out of Scope

- Frontend visual redesign (separate PR)
- Adding more RAG sources
- Switching from OpenAI to Claude API (pending funding)
- Multi-turn conversation context sent to LLM (stored but not sent)

## Sources & References

### Internal References

- **PRD:** `docs/planning/PRD_ASK_MENO_V2.md`
- **Reference implementation:** `docs/planning/ask_meno_v2_schema.py` — new models + all 4 static prompt layers
- **Current models:** `backend/app/models/chat.py` (StructuredClaim line 8, StructuredSection line 15, StructuredLLMResponse line 22)
- **Current prompts:** `backend/app/llm/system_prompts.py` (LAYER_1 line 13, LAYER_2 line 19, LAYER_3 line 99)
- **Prompt assembly:** `backend/app/services/prompts.py:17` — `build_system_prompt()`
- **Citation rendering:** `backend/app/services/citations.py:396` — `render_structured_response()`
- **LLM call params:** `backend/app/services/ask_meno.py:241` — `max_tokens`, `temperature`
- **Frontend rendering:** `frontend/src/routes/(app)/ask/+page.svelte:132` — `renderContent()`
- **Citation tests (no render test):** `backend/tests/services/test_citations.py`
- **Ask meno service tests:** `backend/tests/services/test_ask_meno_service.py:39` — `LLM_RAW_JSON` to update
- **Guardrails integration tests:** `backend/tests/api/routes/test_chat_guardrails.py` — imports to fix
