# PRD: Appointment Prep Flow Refactor
**Meno — Internal Product Document**
**Status: Draft**

---

## Problem Statement

The appointment prep flow produces output that does not match its stated purpose. The narrative — the only piece of the flow the user can see and edit — disappears into a downstream LLM call and never appears verbatim in either document. The user has no idea what they are building, what they will receive, or why anything they do in the wizard matters. The scenario responses cite research without sourcing it. The input model captures frequency statistics but not the qualitative, personal detail that makes appointment prep materials actually useful to a provider.

The gold standard for what this feature should produce already exists: the manually-generated document from the dogfooding session. This PRD defines the work required to close that gap systematically.

---

## Goals

- User understands what they are building before they start
- Everything the user edits appears verbatim in their output documents
- Provider summary reads like a specific person's story, not a statistics report
- Scenario responses are grounded in actual cited sources via the RAG pipeline
- Input captures enough qualitative detail to produce specific, personal output
- Voice is consistent with Meno throughout — warm, direct, clinically grounded

## Non-Goals

- Prompt voice revision (separate workstream, done collaboratively)
- Symptom severity sliders in the logging flow (future PRD)
- MyChart integration
- Mobile layout changes

---

## Changes by Area

---

### 1. Step 0 — Intro Page (New)

**What:** A new page before the wizard begins, accessible from the nav bar "Appt Prep" link.

**Why:** Users currently enter the wizard with no context about what they are building, how long it takes, or what they will walk away with. This erodes confidence in the process before it begins.

**Content:**

- What appointment prep builds: two documents — a Provider Summary to share with your provider, and a Personal Cheat Sheet to carry into the room
- What each document contains (brief, concrete)
- How long the wizard takes (~5 minutes)
- What data it draws on (symptom logs, medications, your answers)
- A single CTA: "Start your prep"

**Design notes:**

- Surfaces both document names and purposes explicitly
- Tone is Meno's voice — not marketing copy, not a legal disclaimer

---

### 2. Step 1 — No Structural Changes

Appointment type, goal, dismissed before, and urgent symptom fields remain as-is. The urgent symptom conditional field styling can be addressed in a future pass (currently flagged as an open issue).

---

### 3. Step 2 — Narrative (UX Fix + Architectural Fix)

#### 3a. UX Fix — Edit Box Context

**Current state:** The edit box shows generated text with the caption "Edit freely — this is your document." No explanation of where this text goes or why editing matters.

**New state:** Add explicit framing above the edit box:

> "This summary goes directly to your provider's document — word for word. Read it carefully and edit anything that doesn't sound right or doesn't reflect your experience. This is the most important thing you'll do in this process."

Add a secondary note below the text area:

> "Your edits are saved automatically. What you see here is what your provider will read."

#### 3b. Architectural Fix — Narrative Verbatim to Provider PDF

**Current behavior:** Narrative is saved to the database, retrieved in Step 5, and passed as context to the provider summary LLM call, which rewrites it. The narrative never appears verbatim in any output. User edits are lost.

**New behavior:** The narrative text (as edited by the user) goes verbatim into the Provider Summary PDF as the "Symptom Picture" section. The provider summary LLM call is restructured to generate only the sections it should own: opening context paragraph and closing statement. It no longer receives the narrative as something to summarize — it receives it as something already written.

**Impact on `build_provider_summary_user_prompt`:**

- Remove `symptom_picture` from the JSON output schema
- The prompt now generates only `opening` and `closing`
- `key_patterns` (co-occurrence patterns) remains LLM-generated since it requires interpretation of the stats

**Impact on `build_provider_summary_pdf`:**

- Insert narrative text verbatim between opening and key_patterns sections
- Label the section "Symptom Summary" in the PDF

**Impact on `AppointmentPrepNarrativeResponse`:**

- No model changes required — narrative is already saved and retrieved correctly
- The disconnect is entirely in how Step 5 uses it

---

### 4. Step 3 — Prioritize Concerns (Enhancement)

#### 4a. Concern Comments

**Current state:** Concerns are strings. The user drags to reorder but cannot add context to individual items.

**New state:** Each concern card gets an optional inline text field below the concern label.

- Placeholder: "How is this affecting your daily life? (optional)"
- Character limit: 200
- Displayed only when the card is focused or on tap/click (not always visible — keeps the UI clean)

**Data model change:** Concerns change from `string[]` to `object[]`:

```typescript
interface Concern {
  text: string;
  comment?: string;
}
```

**Downstream impact:**

- Both PDF renderers receive concern objects and render comment beneath the concern label in a smaller, secondary style
- All prompt builders that receive `concerns_text` need to format as: `"Joint pain — can't get through a workday without it affecting me"` rather than just `"Joint pain"`
- `build_cheatsheet_user_prompt` and `build_provider_summary_user_prompt` both affected
- `save_concerns` and `get_concerns` in the appointment repository need to handle the new shape

#### 4b. Copy Update

The current instruction "Drag to reorder, or use the arrows. Your top concern will be listed first in your materials." is accurate but undersells why order matters.

New copy: "Put what matters most first. Providers often only get to the first few topics raised — lead with what you need most from this appointment."

---

### 5. Step 3.5 — Conversational Context Step (New)

**What:** A new step between "Prioritize concerns" and "Practice scenarios" that captures qualitative context in Meno's voice rather than form-field style.

**Why:** The gap between current output and the gold standard document is almost entirely explained by missing qualitative input. Frequency statistics tell a provider how often something happens. They don't tell a provider that it's affecting the user's ability to return to work, or that she's already tried four lifestyle interventions, or that she has no personal history of clotting risk.

**Step title:** "A little more about you"

**Step subtitle:** "This helps us write materials that sound like you, not a statistics report."

#### What it captures:

**1. What have you already tried?**

Free text, prompted with examples inline:

> "Tell us what you've already tried for your symptoms — lifestyle changes, supplements, prior medications, other providers, anything. This helps us make sure your materials reflect what you've done, not just what you're experiencing."

Placeholder: "e.g., four days a week of resistance training, tried magnesium glycinate for sleep, saw a gynecologist last year who didn't think my symptoms warranted treatment"

Character limit: 500

**2. Is there anything you specifically want to ask for or walk away with today?**

Free text:

> "If you know what you want from this appointment — a specific prescription, a referral, a test, a plan — say it here. We'll make sure your materials reflect it."

Placeholder: "e.g., I want to discuss starting transdermal estrogen and leave with a prescription if appropriate"

Character limit: 300

**3. Two clinical context questions (yes/no):**

Delivered conversationally, not as a medical intake:

> "Two quick questions that help us make your provider summary accurate:"

- "Do you have a personal history of blood clots or have you been told you have clotting risk?" (Yes / No / Not sure)
- "Do you have a personal or strong family history of breast cancer?" (Yes / No / Not sure)

If the user selects Yes to either: surface a brief inline note — "We'll make sure your materials note this. Discuss with your provider how it affects your options." No further action required from the app.

All three free-text fields must be sanitized using the refactored `sanitize_prompt_input` function (see Implementation Notes). Character limits are enforced at both the UI and sanitization layer.

**Data model additions to `AppointmentContext`:**

```python
what_have_you_tried: str | None = None
specific_ask: str | None = None
history_clotting_risk: str | None = None   # "yes" | "no" | "not_sure"
history_breast_cancer: str | None = None   # "yes" | "no" | "not_sure"
```

**Downstream impact:**

- `build_narrative_user_prompt` receives `what_have_you_tried` and `specific_ask`
- `build_provider_summary_user_prompt` receives all four fields
- `build_cheatsheet_user_prompt` receives `specific_ask` (drives the "Your Key Ask" section)
- Contraindication flags included in provider summary opening if present

---

### 6. Step 4 — Scenarios (RAG Integration)

**Current state:** `generate_scenario_suggestions` calls OpenAI directly with a prompt that instructs it to cite evidence but provides no actual sources. Output says "research shows" and "NAMS guidelines" without grounding in retrieved content. The `sources` field in the JSON schema exists but is always empty. In practice, the model has hallucinated citations entirely unrelated to menopause — including at least one study about pediatric respiratory infections. The previous mitigation ("CRITICAL: Do NOT include URLs or citations") was added specifically because of this, but removes the evidential value of the responses entirely. The correct fix is grounding, not suppression.

**Why this is a problem:** Users who have been dismissed multiple times are the most likely to fact-check these responses. Vague authority claims from an ungrounded LLM erode exactly the trust this feature is meant to build.

**New behavior:** Each scenario suggestion is generated using the Ask Meno RAG pipeline.

#### Implementation approach:

For each dismissal scenario selected in `_select_scenarios`, before calling the LLM:

1. Use the scenario title as the retrieval query (e.g., "Your symptoms aren't severe enough to treat")
2. Retrieve relevant chunks from the RAG index (same pipeline as Ask Meno)
3. Include retrieved chunks in the scenario suggestion prompt as source documents
4. Instruct the LLM to ground its response only in the provided sources
5. Populate the `sources` field with actual source metadata from the retrieved chunks

**Prompt changes:**

- `SCENARIO_SUGGESTIONS_SYSTEM` is restructured to follow the one-source-per-claim model used in Ask Meno's `LAYER_3_SOURCE_RULES`
- The instruction to "reference specific research/statistics" is replaced with "use only the provided source documents"
- "CRITICAL: Do NOT include URLs or citations" is replaced with structured source attribution

**Output schema change:**

```python
{
  "scenario_title": str,
  "suggestion": str,
  "sources": [{"title": str, "excerpt": str}]  # populated from RAG retrieval
}
```

**Display change (Step 4 UI):**

Source citations displayed beneath each scenario card in a small, secondary style. Not a full citation — just enough to signal this is grounded: "Based on: NAMS 2022 Position Statement on MHT."

**Fallback:** If RAG retrieval returns no relevant chunks for a scenario, the suggestion is generated without source grounding and the `sources` field remains empty. No fabricated citations. The UI does not display a source badge for unsourced scenarios.

---

### 7. Step 5 — Results Screen

No structural changes to the results screen layout. The download links for Provider Summary and Personal Cheat Sheet remain as-is.

**Copy change:** "Take these documents to your appointment." is adequate but generic.

New subtitle beneath the checkmark: "Your Provider Summary is ready to email ahead or hand to your provider. Your Personal Cheat Sheet is yours to carry in."

---

## Data Flow Summary (Post-Refactor)

```
Step 0  Intro
Step 1  Context (appointment type, goal, dismissed before, urgent symptom)
         → saved to AppointmentContext
Step 2  Narrative generated from symptom logs + context
         → user edits
         → saved verbatim to database
         → goes verbatim into Provider Summary PDF (Symptom Picture section)
Step 3  Concerns prioritized with optional per-concern comments
         → saved as Concern[]
         → rendered verbatim in both PDFs with comments inline
Step 3.5 Qualitative context (tried, specific ask, contraindications)
         → saved to AppointmentContext
         → feeds narrative prompt, provider summary prompt, cheatsheet prompt
Step 4  Scenarios generated via RAG pipeline with real source grounding
         → saved with source metadata
         → rendered in Cheat Sheet "If Things Go Sideways" section
Step 5  LLM generates:
         - Provider Summary: opening + key_patterns + closing (narrative is verbatim, not rewritten)
         - Cheatsheet: opening_statement + question_groups (driven by concerns + specific_ask)
         PDFs built and uploaded
         User downloads both
```

---

## What the LLM Owns vs. What Goes Verbatim

| Section | Source |
|---|---|
| Provider Summary — Opening | LLM (from context + contraindications) |
| Provider Summary — Symptom Picture | User-edited narrative, verbatim |
| Provider Summary — Key Patterns | LLM (co-occurrence interpretation) |
| Provider Summary — Closing | LLM (from specific_ask + concerns) |
| Provider Summary — Concerns table | User input, verbatim |
| Provider Summary — Frequency table | Computed stats, no LLM |
| Cheat Sheet — Opening statement | LLM (from context + specific_ask) |
| Cheat Sheet — Most frequent symptoms | Computed stats, no LLM |
| Cheat Sheet — Concerns | User input, verbatim |
| Cheat Sheet — Questions | LLM (from concerns + comments + specific_ask) |
| Cheat Sheet — If Things Go Sideways | RAG-grounded LLM |
| Cheat Sheet — What to bring | Static template |

---

## Open Questions

1. **Step 3.5 placement:** Resolved — the qualitative context step comes after "Prioritize concerns." Prioritization is quick and gives the user a frame of reference for the open-text questions.

2. **Narrative tone:** Resolved — the narrative should read naturally to both a provider and a patient. The current output is too clinical. This is the first prompt to revise in the separate prompt workstream.

3. **Contraindication display in PDFs:** Unresolved — flagged for discussion before implementation. If a user indicates clotting risk or breast cancer history, it is unclear whether this should appear as a flagged item in the Provider Summary or simply inform the prose. Clinical sensitivity and liability implications need to be considered before this is built.

4. **RAG index coverage for scenarios:** NAMS guidelines are not yet indexed — this is a known gap to address before shipping Step 4. The Menopause wiki and a substantial paper collection are already indexed and should provide reasonable coverage for most scenario types. Confirm coverage before launch.

---

## Prompt Revision Workstream (Separate)

The following prompts are flagged for revision in a separate pass, reviewed collaboratively rather than delegated to Claude Code:

1. `NARRATIVE_SYSTEM` + `build_narrative_user_prompt` — voice shift, richer context inputs
2. `SCENARIO_SUGGESTIONS_SYSTEM` + `build_scenario_suggestions_user_prompt` — RAG-grounded rewrite
3. `PROVIDER_SUMMARY_SYSTEM` + `build_provider_summary_user_prompt` — restructured (no longer owns symptom picture)
4. `CHEATSHEET_SYSTEM` + `build_cheatsheet_user_prompt` — aligned to gold standard output
5. `SYMPTOM_SUMMARY_SYSTEM` + `build_symptom_summary_user_prompt` — export flow, separate pass
6. `PROVIDER_QUESTIONS_SYSTEM` + `build_provider_questions_user_prompt` — export flow, separate pass

---

## Implementation Notes

### Sanitization Refactor

`backend/app/utils/sanitize.py` currently contains two functions. Before implementing any new user-generated text inputs, refactor `sanitize_prompt_input` to accept a `max_length` parameter rather than hardcoding a character limit. The existing calls throughout the codebase should pass their current limit explicitly so behavior is unchanged.

All new free-text fields introduced in this PRD — concern comments (Step 3), and the three fields in Step 3.5 (`what_have_you_tried`, `specific_ask`, and the contraindication questions) — must use this refactored function with their respective character limits passed as the parameter. Do not create new sanitization functions for these inputs.

---

*Prepared with Meno · Internal use only*