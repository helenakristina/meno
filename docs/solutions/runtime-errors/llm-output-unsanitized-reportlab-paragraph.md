---
title: LLM Output Passed Unsanitized to ReportLab Paragraph()
category: runtime-errors
date: 2026-04-08
tags: [pdf, reportlab, llm, sanitization, appointment-prep]
modules: [app/services/pdf.py, appointment-prep]
---

## Problem

ReportLab's `Paragraph()` constructor parses its text argument as XML-like markup. LLM-generated strings (`content.opening`, `content.key_patterns`) were passed directly to `Paragraph()` in `build_provider_summary_pdf()` without any escaping.

If the LLM produces output containing XML-like tags — `<b>`, `<font color="red">`, bare `&` — whether through hallucination, model drift, or indirect prompt injection via a RAG chunk, ReportLab will:
- Silently change PDF formatting (unexpected bold, font color, etc.), or
- Raise `ValueError: XML syntax error` on malformed/unbalanced tags, surfacing as a 500 to the user

This was discovered during code review of the Phase 5 `closing` field removal. Removing `closing` reduced the exposed surface from 3 LLM fields to 2, but the root issue remained.

## Root Cause

ReportLab's `Paragraph` class is XML-aware by design — it supports inline markup like `<b>`, `<i>`, `<font>`, `<br/>` for rich formatting. Any LLM-generated string that accidentally contains these patterns will be interpreted as intentional markup rather than literal text.

The same issue applies to `content.opening_statement` in `build_cheatsheet_pdf()`.

Note: **user-authored text** going through `_inline_md()` is intentionally XML-tagged (that function generates ReportLab markup). Only **LLM JSON response fields** going directly to `Paragraph()` are the problem.

## Solution

Add a module-level `_strip_llm_tags()` helper in `pdf.py` that strips XML-like tags from LLM output before it reaches `Paragraph()`:

```python
def _strip_llm_tags(text: str) -> str:
    """Strip XML-like tags from LLM output to prevent ReportLab parse errors."""
    return re.sub(r"<[^>]+>", "", text).strip()
```

Apply it to every LLM JSON field passed directly to `Paragraph()`:

```python
# build_provider_summary_pdf
story.append(Paragraph(_strip_llm_tags(content.opening), body_style))
story.append(Paragraph(_strip_llm_tags(content.key_patterns), body_style))

# build_cheatsheet_pdf
story.append(Paragraph(_strip_llm_tags(content.opening_statement), body_style))
```

The `re` module is already imported in `pdf.py`. The pattern is identical to the one used in `_sanitize_prompt_input()` in `appointment_prompts.py` — same concern, opposite direction (user input → prompt vs. LLM output → PDF).

**What to leave untouched:**
- `narrative` parameter — user-authored text that goes through `_inline_md()` intentionally
- Concern text — user-authored, already sanitized before LLM calls
- Question group questions — go through string interpolation, not raw `Paragraph()` wrapping of LLM fields

## Prevention

**Rule:** Any LLM JSON field passed directly to ReportLab `Paragraph()` must go through `_strip_llm_tags()` first.

**When adding new LLM response fields to a PDF builder:**
1. Check whether the field is passed directly to `Paragraph()` (as opposed to going through `_inline_md()`)
2. If yes, wrap it in `_strip_llm_tags()`
3. Add a test that passes XML-like content in that field and asserts the PDF builds:

```python
def test_survives_llm_output_with_xml_tags(self, svc):
    # CATCHES: ReportLab ValueError when LLM returns XML-like tags
    result = svc.build_provider_summary_pdf(
        content=_provider_content(
            opening="Patient has <b>severe</b> hot flashes & night sweats.",
            key_patterns="Hot flashes <i>often</i> co-occur with sweats.",
        ),
        narrative=_NARRATIVE,
        frequency_stats=[],
        cooccurrence_stats=[],
        concerns=[],
    )
    assert result[:4] == b"%PDF"
```

## Related

- `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md` — same `re.sub(r'<[^>]+>', '', text)` pattern for sanitizing user input going *into* LLM prompts. Asymmetric concern: that doc covers input sanitization; this covers output sanitization.
- `backend/app/llm/appointment_prompts.py` — `_sanitize_prompt_input()` at lines 28–44 is the reference implementation of this pattern
