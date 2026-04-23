---
title: "Pydantic optional date field: str(None) produces literal 'None' string"
category: logic-errors
date: 2026-04-22
tags:
  [pydantic, python, optional-fields, llm-prompt, medication, context-builder]
---

# Pydantic Optional Date Field: `str(None)` Footgun

## Problem

When formatting a `date | None` field into a string for LLM prompt injection, `str(None)` produces the string `"None"` — which is truthy and passes through `sanitize_prompt_input` unchanged. The LLM receives nonsensical output like `"stopped None"` instead of a meaningful fallback.

```python
# MedicationResponse.end_date is typed `date | None`
end = sanitize_prompt_input(str(med.end_date), max_length=50)
# When end_date is None → str(None) = "None" → sanitize_prompt_input("None") = "None"
# Prompt receives: "stopped None"
```

`sanitize_prompt_input` only returns `"not provided"` for _falsy_ inputs. The string `"None"` is truthy, so it passes through unmodified.

## Root Cause

A prior fix removed a wrong `isinstance(med.end_date, str)` guard and replaced it with `str(med.end_date)` unconditionally — which was the correct fix for the isinstance bug but introduced this edge case for the `None` branch.

The field is typed `date | None` in the Pydantic model. In production, `recent_changes` medications always have an end_date (they were stopped), but the model allows `None` and it is a valid state.

## Fix

Guard before converting:

```python
# context_builder.py
end = sanitize_prompt_input(
    str(med.end_date) if med.end_date else "date unknown",
    max_length=50,
)
```

## Pattern: Safe Optional Date Formatting

Any time you format a `date | None` field for display or LLM injection:

```python
# ✅ Correct — explicit guard
value = str(field) if field else "date unknown"

# ✅ Also correct — if sanitize_prompt_input handles None (check its signature)
value = sanitize_prompt_input(str(field) if field else "", max_length=50)

# ❌ Wrong — str(None) = "None" (truthy, passes sanitizer)
value = sanitize_prompt_input(str(field), max_length=50)
```

## Prevention

- When formatting `Optional` fields into strings, always guard for `None` _before_ calling `str()` — never after.
- Test cases for optional Pydantic fields should always include a `None` value, especially when the field feeds into LLM prompts or user-visible strings.
- Add a test in the `TestMedicationBlock` (or equivalent) that exercises `end_date=None` and asserts a meaningful fallback string appears in the output, not `"None"`.
