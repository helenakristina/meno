---
status: pending
priority: p2
issue_id: "090"
tags: [code-review, backend, dead-code, maintainability]
dependencies: []
---

# Dead `narrative` parameter in `generate_provider_summary_content`

## Problem Statement

`generate_provider_summary_content` in `llm.py` accepts `narrative: str` as its first parameter. The parameter is never forwarded to the prompt builder — `build_provider_summary_user_prompt` has no `narrative` parameter, and the docstring was updated to note "narrative inserted verbatim by PDF builder." But the parameter, the docstring entry for it, and the caller (`appointment.py:570`) all still reference it.

Flagged by Python reviewer, architecture reviewer, and simplicity reviewer.

## Findings

- **File**: `backend/app/services/llm.py`, lines 375–376 (signature), ~412 (build call)
- `appointment.py:570`: `provider_task = self.llm_service.generate_provider_summary_content(narrative=narrative_text, ...)` — passes it but it has no effect
- A developer reading the signature would assume the narrative influences the LLM output; it does not
- The stale docstring reinforces this misunderstanding

## Proposed Solution

Remove `narrative` from `generate_provider_summary_content`'s signature, update the docstring, and remove `narrative=narrative_text` from the call site in `appointment.py`.

```python
# llm.py — remove 'narrative' param
async def generate_provider_summary_content(
    self,
    concerns: list[str],
    appointment_type: str,
    ...

# appointment.py — remove narrative= kwarg
provider_task = self.llm_service.generate_provider_summary_content(
    concerns=concerns_for_llm,
    ...
```

Also update tests in `test_appointment_service.py` and `test_pdf_service.py` that pass `narrative=` to this method.

## Acceptance Criteria

- [ ] `narrative` parameter removed from `generate_provider_summary_content` signature
- [ ] Docstring updated to remove the `narrative` arg description and the now-stale `symptom_picture` mention
- [ ] Call site in `appointment.py` updated
- [ ] All test mocks updated
- [ ] All 1070 backend tests still pass
