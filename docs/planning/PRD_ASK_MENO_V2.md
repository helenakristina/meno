# PRD: Ask Meno v2 — Voice-Forward Response Schema

## Summary

Refactor Ask Meno's RAG pipeline to produce warm, conversational, paragraph-style responses instead of clinical bullet-point claims. Migrate from per-claim citation mapping to a one-paragraph-one-source model that maintains citation integrity while enabling natural voice.

## Problem

Ask Meno currently returns responses as individual claims in bullet-point format. Each claim maps to one or more source indices. This produces accurate but clinical-sounding output that reads like a medical database, not a supportive conversation. The tone doesn't match Meno's mission of being a warm, knowledgeable guide for women navigating menopause.

Example of current output:

- "MHT is generally well-tolerated with minimal side effects for the majority and has the potential to greatly increase quality of life. [1]"
- "Current recommendations endorse the use of MHT in recently menopausal women with appropriate indications. [2]"

Example of desired output:
"Most women tolerate MHT really well, and for a lot of us it's a game-changer for quality of life. Current guidelines support starting MHT when you're symptomatic and within the window of opportunity — before 60 and within 10 years of menopause."

## Architecture Changes

### 1. Response Schema (backend/app/models/chat.py)

Replace the existing claim-based models with paragraph-based models.

**Remove these models:**

- `StructuredClaim`
- `StructuredSection`
- `StructuredLLMResponse`

**Add these models:**

```python
class ResponseSection(BaseModel):
    """A paragraph drawn from exactly ONE source."""
    heading: str | None = None
    body: str = Field(
        description="Conversational paragraph in Meno's voice. Plain text, no markdown."
    )
    source_index: int | None = Field(
        default=None,
        description="1-based index of the single source this section draws from. null only for closing/disclaimer."
    )


class StructuredLLMResponse(BaseModel):
    """Complete structured response from the LLM. Replaces the old claim-based version."""
    sections: list[ResponseSection] = Field(default_factory=list)
    disclaimer: str | None = None
    insufficient_sources: bool = False
```

**Keep unchanged:** `Citation`, `ChatMessage`, `ChatRequest`, `ChatResponse`, `ConversationSummary`, `ConversationListResponse`, `ConversationMessagesResponse`, `SuggestedPromptsResponse`

### 2. System Prompts (backend/app/llm/system_prompts.py)

Replace the existing three layers with five layers. See the reference implementation attached as `docs/planning/ask_meno_v2_schema.py` for the full prompt text.

**Layer 1 — Identity:** Who Meno is. Warm, informed friend, not a medical professional.

**Layer 2 — Voice:** How Meno speaks. Includes explicit before/after examples and anti-patterns to avoid (no "It is important to note that", no reflexive "consult your healthcare provider" on every response, no markdown formatting). This is the new layer that doesn't exist in v1.

**Layer 3 — Source Rules:** The JSON schema, one-source-per-section rule, citation verification checklist. Replaces the old LAYER_2 with the new schema structure (body + source_index instead of claims + source_indices array).

**Layer 4 — Scope:** In-scope and out-of-scope topics, diagnosis rule, WHI study context note. Same content as old LAYER_3 but cleaned up.

**Layer 5 — Dynamic context:** Built at runtime. Same as old LAYER_4 — user context, cycle data, medications, RAG chunks. This is assembled by the PromptService.

### 3. Prompt Service (backend/app/services/prompts.py)

Update `PromptService.build_system_prompt()`:

- Import the new layer constants: `LAYER_1_IDENTITY`, `LAYER_2_VOICE`, `LAYER_3_SOURCE_RULES`, `LAYER_4_SCOPE`
- The dynamic context assembly (user context, cycle data, medications, RAG chunks) stays the same — it becomes the fifth layer
- Join all five layers with `"\n\n"` separator (current behavior uses same join)

The method signature and all parameters stay the same. Only the imported layer constants and the join order change.

### 4. Citation Service (backend/app/services/citations.py)

Update `CitationService.render_structured_response()` to work with the new schema:

**Old behavior:** Iterates over sections → claims, renders each claim as a bullet point, attaches source indices per claim.

**New behavior:** Iterates over sections, renders each section's `body` as a paragraph, attaches the single `source_index` as a citation. If a section has a `heading`, render it as a line before the paragraph (plain text, no markdown — the frontend handles formatting).

The method should:

1. For each section with a non-null `source_index`, look up the source in the chunks list and create a `Citation` object
2. Deduplicate citations (same source used in multiple sections should appear once in the citations list)
3. Return the rendered text as joined paragraphs and the deduplicated citation list

The fallback pipeline (lines 299-318 in ask_meno.py) stays as-is for graceful degradation.

### 5. Ask Meno Service (backend/app/services/ask_meno.py)

Minimal changes:

- The `StructuredLLMResponse` import at the top already points to `chat.py` — it will pick up the new model automatically
- Consider increasing `max_tokens` from 1500 to 2000 (paragraph responses may run slightly longer)
- Consider increasing `temperature` from 0.3 to 0.5 (allows more natural paraphrasing while maintaining source faithfulness)

### 6. Frontend Rendering

The frontend currently renders claims as bullet points with superscript citation markers. Update to:

- Render each section as a paragraph (or short block)
- If a section has a `heading`, render it as a styled heading above the paragraph
- Attach the source citation as a footnote marker at the end of the paragraph (same as current per-claim markers, just at paragraph level)
- Strip any markdown that might leak through (bold, headers, etc.) — the prompt says plain text only, but belt and suspenders

## Key Constraints

- **One source per section.** Each section's body draws from exactly one source document. This is the core architectural constraint that maintains citation integrity.
- **Plain text only.** The model returns plain text in body fields. No markdown formatting. The frontend controls all visual presentation.
- **No reflexive disclaimers.** The "consult your healthcare provider" redirect should only appear when the question is genuinely about personal dosing, diagnosis, or risk assessment — not appended to every educational answer.
- **Voice consistency.** Meno sounds like a warm, knowledgeable friend who's been through it and done the research. Not a medical textbook. Not a chatbot. Not ChatGPT saying "hello, warrior."
- **Backward compatibility.** The fallback pipeline for non-JSON responses stays intact. The `ChatResponse`, `ChatMessage`, and `Citation` models are unchanged, so the API contract with the frontend doesn't break.

## Testing Strategy

Follow TDD. For each test, write a CATCHES annotation describing the specific bug it prevents.

### Unit Tests

**System prompts:**

- Test that all five layers are present in the assembled prompt
- Test that dynamic context (user context, cycle data, medications, chunks) is correctly formatted
- Test that voice examples are included in the prompt

**Response parsing:**

- Test that a valid v2 JSON response parses into the new `StructuredLLMResponse`
- Test that sections with `source_index` produce correct citations
- Test that sections with `null` source_index (disclaimer/closing) don't produce citations
- Test that the old v1 format fails validation (catches accidental regression to old schema)

**Citation service:**

- Test that `render_structured_response` produces paragraph text (not bullet points)
- Test that citations are deduplicated when multiple sections reference the same source
- Test that headings are rendered correctly when present
- Test that headings are omitted when null

### Integration Tests

- Test the full ask() flow with mock LLM returning v2 JSON format
- Test the fallback pipeline still works when LLM returns non-JSON
- Test that the response renders correctly with real RAG chunks

## Out of Scope

- Frontend visual redesign (separate PR)
- Adding more sources to the RAG pipeline
- Switching from OpenAI to Claude API (separate effort, pending funding)
- Multi-turn conversation context sent to LLM (currently only stored, not sent)

## Reference Files

- `meno_ask_schema_v2.py` — Full reference implementation of the new Pydantic models and system prompt layers
- `backend/app/models/chat.py` — Current models to be updated
- `backend/app/llm/system_prompts.py` — Current prompts to be replaced
- `backend/app/services/prompts.py` — Current prompt assembly service
- `backend/app/services/ask_meno.py` — Orchestration service (minimal changes)
- `backend/app/services/citations.py` — Citation rendering (needs update for new schema)
