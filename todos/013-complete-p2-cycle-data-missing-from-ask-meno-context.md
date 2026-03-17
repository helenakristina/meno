---
status: pending
priority: p2
issue_id: "013"
tags: [code-review, backend, agent-native, llm-context]
dependencies: []
---

# Inject cycle analysis and `has_uterus` into Ask Meno LLM context (Layer 4)

## Problem Statement

The Ask Meno system prompt's Layer 4 (dynamic context) only injects `journey_stage`, `age`, and `symptom_summary`. After this branch, users have rich cycle data (`average_cycle_length`, `months_since_last_period`, `inferred_stage`, `has_uterus`) accessible via `GET /api/period/analysis` — but none of it reaches the LLM. A user asking "what does my cycle pattern say about my stage?" gets no useful response because the LLM has no cycle context.

This also creates an agent-native parity gap: the Cycles page UI has a richer view of the user than the conversational AI does.

## Findings

- `backend/app/services/prompts.py:14` — `build_system_prompt` signature has no cycle params
- `backend/app/services/ask_meno.py:109` — `get_context` call does not fetch cycle analysis
- `GET /api/period/analysis` returns rich data but it's never piped into the conversation
- `has_uterus` from user settings also missing from context
- Agent-native reviewer flagged as critical context parity gap

## Proposed Solutions

### Option 1: Add optional cycle context to `build_system_prompt`

**Approach:**
1. Add a `CycleContext` optional dataclass/TypedDict to `prompts.py`
2. In `AskMenoService.ask()`, call `period_repo.get_cycle_analysis(user_id)` (or the analysis service method)
3. Pass `inferred_stage`, `months_since_last_period`, `has_uterus` as optional context into Layer 4
4. Add natural language summary: "User has not had a period in X months. Cycle data suggests [stage]."

**Pros:** Closes context gap, additive and non-breaking (optional params)

**Cons:** Adds one extra DB call per Ask Meno request; only relevant if period tracking is enabled

**Effort:** 2 hours

**Risk:** Low — additive change to system prompt

---

### Option 2: Include cycle summary in existing `get_context` user profile

**Approach:** Add cycle analysis fields to the `UserContext` object returned by `user_repo.get_context()`, then extend the system prompt template to render them.

**Pros:** Single context fetch, unified user profile model

**Cons:** Couples user profile context to period tracking; not all users have period data

**Effort:** 2 hours

**Risk:** Low

## Recommended Action

Option 1: optional `CycleContext` parameter. Check `period_tracking_enabled` from user settings before fetching — skip the DB call if tracking is disabled.

## Technical Details

**Affected files:**
- `backend/app/services/prompts.py` — add cycle context parameter
- `backend/app/services/ask_meno.py` — fetch cycle analysis and pass to prompt builder
- Possibly: `backend/app/repositories/period_repository.py` — `get_cycle_analysis` already exists

## Acceptance Criteria

- [ ] System prompt includes cycle summary when period tracking is enabled and data exists
- [ ] System prompt omits cycle summary when period tracking is disabled or no data
- [ ] `has_uterus` included in LLM context
- [ ] Ask Meno can answer cycle-related questions using the injected context

## Work Log

### 2026-03-16 - Code Review Discovery

**By:** Claude Code (ce-review)

**Actions:**
- Traced period data through API to confirm it never reaches the LLM
- Identified Layer 4 as the insertion point
- Assessed DB call cost (one additional query per chat message)
