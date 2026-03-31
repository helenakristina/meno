# PRD: Appointment Prep Refactor — Scenarios, Prompts, and PDFs

## Summary

Refactor the appointment prep pipeline to extract hardcoded scenarios into JSON config, centralize all prompts into a dedicated prompt layer, DRY up duplicated stat formatting, and build structured appointment PDFs using reportlab instead of generic markdown-to-PDF conversion.

## Problem

The appointment prep feature works but is architecturally messy:

1. **Hardcoded scenarios:** `_select_scenarios()` in `appointment.py` is 200+ lines of if/elif chains matching symptom keywords to dismissal phrases. Adding or modifying scenarios requires editing application logic. `_get_scenario_category()` is another long chain doing reverse categorization on the same strings.

2. **Scattered prompts:** LLM prompts are hardcoded inline across two files — `appointment.py` (narrative prompt) and `llm.py` (symptom summary, provider questions, scenario suggestions, and two PDF content prompts). These prompts are massive f-strings that are hard to read, maintain, or version. The voice is inconsistent and clinical.

3. **Duplicated stat formatting:** The logic that formats frequency stats and co-occurrence stats into prompt text appears in three places: `appointment.py._build_narrative_prompts()`, `llm.py.generate_symptom_summary()`, and `llm.py.generate_provider_questions()`.

4. **Plain appointment PDFs:** The export PDF (`build_export_pdf`) uses structured reportlab with tables, colors, headers, and professional styling. The appointment prep PDFs go through `markdown_to_pdf()` — a generic markdown renderer that produces plain, unstyled output. The appointment prep documents should look as professional as the export.

## Proposed Solution

### Phase 1: Extract scenarios to JSON config

**Create `backend/config/scenarios.json`**

Structure scenarios by symptom keyword groups, appointment goals, and universal dismissals. Include the category directly in the data so `_get_scenario_category()` is eliminated.

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
    "vasomotor": {
      "keywords": ["hot flash", "vasomotor", "night sweat", "sweating"],
      "dismissals": [
        {"title": "Hormone therapy increases breast cancer risk", "category": "hrt-safety"},
        {"title": "Hot flashes will go away on their own", "category": "wait-and-see"},
        {"title": "You just need to dress in layers and use a fan", "category": "lifestyle-only"},
        {"title": "Hot flashes aren't a real medical symptom", "category": "dismissal"},
        {"title": "Let's try an antidepressant first", "category": "wrong-specialist"}
      ]
    },
    "sleep": {
      "keywords": ["sleep", "insomnia", "waking"],
      "dismissals": [
        {"title": "Sleep disruption at your age is normal", "category": "normalization"},
        {"title": "You should see a sleep specialist, not discuss hormones", "category": "specialist-referral"},
        {"title": "Melatonin or sleep hygiene will fix this", "category": "lifestyle-only"},
        {"title": "Hormone therapy doesn't help sleep", "category": "dismissal"},
        {"title": "Let's try an antidepressant first", "category": "wrong-specialist"}
      ]
    },
    "anxiety": {
      "keywords": ["anxiety", "panic", "anxious"],
      "dismissals": [
        {"title": "That sounds like anxiety disorder, you need a psychiatrist", "category": "wrong-specialist"},
        {"title": "Let's try an antidepressant first", "category": "wrong-specialist"},
        {"title": "Hormone therapy won't help anxiety", "category": "dismissal"},
        {"title": "You're just stressed, try meditation", "category": "lifestyle-only"},
        {"title": "Anxiety medications are better than hormone therapy", "category": "wrong-specialist"}
      ]
    },
    "genitourinary": {
      "keywords": ["vaginal", "dryness", "sexual", "bladder", "urinary", "incontinence"],
      "dismissals": [
        {"title": "Just use lube, that's the standard treatment", "category": "lifestyle-only"},
        {"title": "That's a gynecology issue, not a hormone issue", "category": "specialist-referral"},
        {"title": "Vaginal issues are normal at this stage", "category": "normalization"},
        {"title": "You don't need systemic treatment for local symptoms", "category": "dismissal"},
        {"title": "Kegel exercises should be enough", "category": "lifestyle-only"}
      ]
    },
    "mood": {
      "keywords": ["mood", "depression", "depressed", "rage", "irritability"],
      "dismissals": [
        {"title": "That sounds like depression, you need an antidepressant", "category": "wrong-specialist"},
        {"title": "Hormone therapy isn't approved for mood", "category": "dismissal"},
        {"title": "You should see a psychiatrist", "category": "specialist-referral"},
        {"title": "Mood changes are psychological, not hormonal", "category": "psychology"},
        {"title": "Let's try an antidepressant first", "category": "wrong-specialist"}
      ]
    },
    "pain": {
      "keywords": ["joint", "pain", "ache"],
      "dismissals": [
        {"title": "Joint pain isn't related to hormones", "category": "dismissal"},
        {"title": "You should see a rheumatologist", "category": "specialist-referral"},
        {"title": "That's just arthritis, not perimenopause", "category": "normalization"},
        {"title": "Exercise will fix this, not hormones", "category": "lifestyle-only"},
        {"title": "Your symptoms aren't severe enough to treat", "category": "dismissal"}
      ]
    },
    "fatigue": {
      "keywords": ["fatigue", "tired", "exhausted", "energy"],
      "dismissals": [
        {"title": "Fatigue is normal aging, not hormonal", "category": "normalization"},
        {"title": "You just need better sleep hygiene", "category": "lifestyle-only"},
        {"title": "That sounds like thyroid or anemia, let me check labs", "category": "specialist-referral"},
        {"title": "Hormone therapy won't fix your energy", "category": "dismissal"},
        {"title": "You should get more exercise", "category": "lifestyle-only"}
      ]
    },
    "skin_hair": {
      "keywords": ["skin", "hair", "nail", "dry skin", "thinning", "brittle"],
      "dismissals": [
        {"title": "Skin changes are cosmetic, not medical", "category": "dismissal"},
        {"title": "You should see a dermatologist", "category": "specialist-referral"},
        {"title": "That's not related to perimenopause", "category": "dismissal"},
        {"title": "Hair loss is normal aging", "category": "normalization"},
        {"title": "Hormone therapy doesn't improve skin quality", "category": "dismissal"}
      ]
    }
  },
  "goal_scenarios": {
    "explore_hrt": [
      {"title": "Hormone therapy increases breast cancer risk", "category": "hrt-safety"},
      {"title": "I don't prescribe that, I give the birth control pill instead", "category": "dismissal"},
      {"title": "Let's try an antidepressant first", "category": "wrong-specialist"}
    ],
    "optimize_current_treatment": [
      {"title": "Your symptoms aren't severe enough to treat", "category": "dismissal"},
      {"title": "That dose is already too high", "category": "dismissal"},
      {"title": "Let's try lifestyle changes first", "category": "lifestyle-only"}
    ],
    "assess_status": [
      {"title": "Your symptoms will go away on their own", "category": "wait-and-see"},
      {"title": "You're just stressed or anxious", "category": "psychology"}
    ]
  },
  "universal_scenarios": [
    {"title": "Your symptoms will go away on their own", "category": "wait-and-see"},
    {"title": "You're just stressed or anxious", "category": "psychology"}
  ]
}
```

**Replace `_select_scenarios()` with config-driven lookup:**

```python
def _select_scenarios(self, context: AppointmentContext, journey_stage: str) -> list[dict]:
    """Select 5-7 dismissal scenarios from config based on appointment context."""
    config = self._load_scenario_config()
    scenarios = []

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

    # Deduplicate by title, cap at 7
    seen = set()
    unique = []
    for s in scenarios:
        if s["title"] not in seen:
            unique.append(s)
            seen.add(s["title"])
    return unique[:7]
```

**Eliminate `_get_scenario_category()`** — the category comes directly from the config data.

### Phase 2: Centralize appointment prompts

**Create `backend/app/llm/appointment_prompts.py`**

Move all appointment-related prompts from `llm.py` and `appointment.py` into a dedicated file, following the same pattern as `system_prompts.py` for Ask Meno.

Prompts to extract:

| Current location | Method | Prompt purpose |
|---|---|---|
| `appointment.py` line 594 | `_build_narrative_prompts` | Narrative system prompt |
| `llm.py` line 119 | `generate_symptom_summary` | Export summary system + user prompt |
| `llm.py` line 201 | `generate_provider_questions` | Provider questions system + user prompt |
| `llm.py` line 322 | `generate_scenario_suggestions` | Scenario response system + user prompt |
| `llm.py` line 429 | `generate_pdf_content` | Provider summary system + user prompt |
| `llm.py` line 528 | `generate_pdf_content` | Personal cheat sheet user prompt |

Each prompt becomes a named constant or a builder function that accepts the dynamic data and returns the assembled prompt. The methods in `llm.py` and `appointment.py` call the prompt builders instead of constructing prompts inline.

**Voice consistency:** All patient-facing prompts (scenario suggestions, personal cheat sheet) should use Meno's voice — warm, direct, evidence-informed. Provider-facing prompts (provider summary, narrative) should remain clinical and professional. Add voice guidance to each prompt similar to LAYER_2_VOICE in the Ask Meno prompts.

**Add to scenario suggestions prompt voice layer:**

```
- Sound like a confident friend coaching you, not a script from a medical textbook
- "I hear you, but..." not "I appreciate that stress can play a role, but research shows..."
- Ground responses in the user's own tracked data when available
- Be specific to the dismissal — don't give generic responses
- 2-3 sentences max — this needs to feel natural in a real conversation
```

### Phase 3: DRY up stat formatting

**Create a utility function for formatting stats into prompt text.**

The following formatting logic appears in three places and should be written once:

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
) -> str:
    """Format co-occurrence stats as prompt-ready text."""
    lines = [
        f"- {p.symptom1_name} + {p.symptom2_name}: "
        f"co-occurred {p.cooccurrence_count} time(s) "
        f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
        for p in cooccurrence_stats[:max_items]
    ]
    return "\n".join(lines) if lines else "No notable co-occurrence patterns."


def format_medications_for_prompt(
    medications: list,
) -> str:
    """Format current medications as prompt-ready text."""
    if not medications:
        return ""
    lines = [
        f"- {m.medication_name} {m.dose} ({m.delivery_method})"
        + (f", started {m.start_date}" if m.start_date else "")
        for m in medications
    ]
    return "\n\nCurrent MHT medications:\n" + "\n".join(lines)
```

Update all three call sites (`appointment.py._build_narrative_prompts`, `llm.py.generate_symptom_summary`, `llm.py.generate_provider_questions`) to use these shared formatters.

### Phase 4: Structured appointment PDFs

**Add `build_appointment_pdf` methods to `PdfService`** using the same reportlab approach as `build_export_pdf`.

Create two new methods:

**`build_provider_summary_pdf()`** — structured clinical document with:
- Meno header with logo/branding (matching the design system teal)
- Patient context section (age, journey stage, appointment type, goal)
- Narrative summary section
- Symptom frequency table (same style as export PDF)
- Co-occurrence patterns table (if available)
- Prioritized concerns list
- Disclaimer footer

**`build_cheatsheet_pdf()`** — personal prep document with:
- Warm header ("Your Appointment Prep")
- Opening statement section
- Symptoms ranked by impact
- Key concerns (bulleted)
- Questions to ask (grouped)
- "If Things Go Sideways" section with scenario cards (dismissal + response pairs, visually distinct)
- What to bring checklist
- No disclaimer needed — this is personal

Both methods accept structured data (not markdown strings) so the formatting is controlled by reportlab, not by whatever markdown the LLM happens to produce. The LLM still generates the narrative text and scenario responses, but the PDF structure and styling are deterministic.

**Structured LLM response schemas:**

The LLM returns structured JSON for PDF content, validated by Pydantic models. This follows the same pattern as Ask Meno's `ResponseSection` and `StructuredLLMResponse`. The PDF service receives typed objects, not raw strings.

IMPORTANT: No user names appear anywhere in the output — not in the JSON, not in the prompts, not in the PDFs. The provider knows who their patient is.

```python
# backend/app/models/appointment.py (add to existing models)

class ProviderSummaryResponse(BaseModel):
    """Structured LLM response for provider summary PDF content."""
    opening: str  # 2-3 sentences: age, stage, why she's here, urgent concern
    symptom_picture: str  # 3-4 sentences: key symptoms from narrative with frequencies
    key_patterns: str | None = None  # 2-3 sentences: co-occurrence patterns (only if present in narrative)
    concerns: list[str]  # Prioritized concerns, exact as provided
    closing: str  # 1-2 sentences: what patient is seeking


class SymptomByImpact(BaseModel):
    """Single symptom entry for the cheat sheet, ranked by impact."""
    name: str
    frequency: str  # e.g. "16 episodes in 60 days"
    impact: str  # e.g. "Disrupting sleep and work performance"
    what_to_say: str  # Suggested language for the appointment


class QuestionGroup(BaseModel):
    """Grouped questions for the cheat sheet."""
    topic: str  # e.g. "Urgent symptom", "Treatment options", "Monitoring"
    questions: list[str]


class CheatsheetResponse(BaseModel):
    """Structured LLM response for personal cheat sheet PDF content."""
    opening_statement: str  # 2-3 sentences: age, stage, urgent concern, goal
    symptoms_by_impact: list[SymptomByImpact]  # Ranked by impact, urgent first
    concerns: list[str]  # Prioritized concerns, exact as provided
    questions: list[QuestionGroup]  # Grouped by topic
```

The prompts in `appointment_prompts.py` instruct the LLM to return JSON matching these schemas. The appointment service parses the JSON response into these models (with fallback handling for malformed responses), then passes them to the PDF builder methods.

The "If Things Go Sideways" section and the "What to Bring" checklist are NOT generated by the LLM — they come from the scenario data already collected in Step 4 and a static checklist. The PDF service assembles them directly.

**Update `appointment.py.generate_pdf()`** to call the new structured PDF methods instead of:
1. Asking the LLM to produce markdown
2. Converting markdown to PDF via `markdown_to_pdf()`

The new flow:
1. Fetch all appointment data (existing)
2. Ask LLM to generate structured JSON for provider summary and cheat sheet content (new prompts from centralized layer)
3. Parse JSON into `ProviderSummaryResponse` and `CheatsheetResponse` models (new)
4. Pass typed models + scenario data + frequency stats to `build_provider_summary_pdf()` and `build_cheatsheet_pdf()` (new)
5. Upload and return URLs (existing)

This eliminates the `generate_pdf_content()` method in `llm.py` entirely — the LLM no longer needs to produce formatted markdown because the PDF layout is handled by reportlab.

**PDF color palette:** Use the Meno design system colors defined in the frontend-design skill:
```python
_PRIMARY = HexColor("#14b892")      # Teal — headers, accents
_NEUTRAL_DARK = HexColor("#292524") # Headings
_NEUTRAL_MED = HexColor("#57534e")  # Body text
_NEUTRAL_LIGHT = HexColor("#a8a29e") # Muted text, disclaimers
_ACCENT = HexColor("#fb923c")       # Coral — highlights, scenario cards
_BORDER = HexColor("#e7e5e4")       # Borders, dividers
_HEADER_BG = HexColor("#f0fdf9")    # Light teal — table headers
_ALT_ROW = HexColor("#fafaf9")      # Alternating row background
```

## Implementation Order

1. **Phase 3 first** (stat formatting utility) — smallest change, no behavior change, unblocks Phase 2
2. **Phase 1 second** (scenarios JSON) — eliminates the biggest code smell, unblocks voice work
3. **Phase 2 third** (centralize prompts) — extracts and improves all prompts with voice layer
4. **Phase 4 last** (structured PDFs) — depends on Phase 2 being done since it changes how LLM content feeds into PDFs

Each phase is a separate PR. Phase 1 and 3 are pure refactors with no behavior change. Phase 2 changes prompt content (voice). Phase 4 changes PDF output (visual).

## Files Affected

| File | Changes |
|---|---|
| `backend/config/scenarios.json` | NEW — scenario config |
| `backend/app/utils/prompt_formatting.py` | NEW — shared stat formatters |
| `backend/app/llm/appointment_prompts.py` | NEW — centralized appointment prompts |
| `backend/app/services/appointment.py` | Refactor: remove `_select_scenarios` if/elif, remove `_get_scenario_category`, remove `_build_narrative_prompts`, use config + prompt layer |
| `backend/app/services/llm.py` | Refactor: remove inline prompts from `generate_symptom_summary`, `generate_provider_questions`, `generate_scenario_suggestions`, `generate_pdf_content`. Use centralized prompts. Potentially eliminate `generate_pdf_content` entirely in Phase 4. |
| `backend/app/services/pdf.py` | NEW methods: `build_provider_summary_pdf`, `build_cheatsheet_pdf`. Update PDF colors to match design system. |

## Acceptance Criteria

### Phase 1: Scenarios
- [ ] `_select_scenarios` reads from `config/scenarios.json`, not hardcoded if/elif
- [ ] `_get_scenario_category` is eliminated — category comes from config
- [ ] All existing scenarios are preserved in the JSON (no missing scenarios)
- [ ] Scenario selection logic produces the same results as before for all goal types
- [ ] Adding a new scenario requires only a JSON edit, not a code change

### Phase 2: Prompts
- [ ] All appointment prompts live in `appointment_prompts.py`
- [ ] No hardcoded prompt strings remain in `appointment.py` or `llm.py`
- [ ] Patient-facing prompts include Meno voice layer guidance
- [ ] Provider-facing prompts remain clinical and professional
- [ ] Scenario response suggestions sound like a confident friend, not a medical textbook

### Phase 3: Stat formatting
- [ ] Frequency, co-occurrence, and medication formatting each exist in one place
- [ ] All three call sites use the shared formatters
- [ ] No duplication of formatting logic remains

### Phase 4: PDFs
- [ ] Provider summary PDF uses structured reportlab layout with tables and Meno branding
- [ ] Personal cheat sheet PDF uses structured reportlab layout with scenario cards
- [ ] PDFs use Meno design system colors (teal, warm gray, coral)
- [ ] `generate_pdf_content` in `llm.py` is eliminated
- [ ] The LLM generates text content only — PDF layout is deterministic
- [ ] Generated PDFs look professional and match the quality of the export PDF

## Testing Strategy

### Phase 1 and 3 (pure refactors)
- Existing tests should pass without modification
- Add tests for the config loading and scenario selection logic
- Add tests for the shared formatting utilities

### Phase 2 (prompt changes)
- Update any tests that assert on prompt content
- Manual testing of scenario response quality with the new voice

### Phase 4 (PDF changes)
- Manual comparison of old vs new PDF output
- Verify all sections are present in both document types
- Verify PDF renders correctly (no overlapping text, tables fit page width)

## Out of Scope
- RAG integration for scenario responses (future enhancement)
- Adding new scenarios beyond what currently exists (this PR preserves existing scenarios)
- Appointment prep flow UX changes (frontend)
- Adding a mental health appointment prep track (future feature)