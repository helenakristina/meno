---
status: pending
priority: p1
issue_id: "084"
tags: [code-review, security, backend, llm, prompt-injection]
dependencies: []
---

# `build_narrative_user_prompt` injects user text without sanitization

## Problem Statement

`what_have_you_tried` and `specific_ask` are interpolated directly into the LLM prompt with no `sanitize_prompt_input()` call. Every other prompt builder in the same file sanitizes these fields. A user who submits `what_have_you_tried = "system: ignore all previous instructions..."` has that string injected raw into the narrative generation prompt.

## Findings

- **File**: `backend/app/llm/appointment_prompts.py`, lines 147–151
- All other builders (`build_provider_summary_user_prompt`, `build_cheatsheet_user_prompt`, `build_scenario_suggestions_user_prompt`) call `sanitize_prompt_input()` on these same fields before interpolation
- This function was missed in Phase 5 when qualitative fields were added

## Proposed Solution

Add `sanitize_prompt_input()` calls on both fields before interpolation, matching the pattern in `build_provider_summary_user_prompt`:

```python
sanitized_tried = sanitize_prompt_input(what_have_you_tried)
sanitized_ask = sanitize_prompt_input(specific_ask)

if sanitized_tried and sanitized_tried != "not provided":
    qualitative_section += f"\nWhat the patient has tried: {sanitized_tried}"
if sanitized_ask and sanitized_ask != "not provided":
    qualitative_section += f"\nPatient's specific ask: {sanitized_ask}"
```

## Acceptance Criteria

- [ ] Both `what_have_you_tried` and `specific_ask` pass through `sanitize_prompt_input` before string interpolation
- [ ] Test added: prompt builder called with injection-attempt string produces sanitized output
- [ ] All existing `test_build_narrative_user_prompt` tests still pass
