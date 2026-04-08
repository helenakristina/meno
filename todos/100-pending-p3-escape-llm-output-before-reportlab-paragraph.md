---
status: pending
priority: p3
issue_id: "100"
tags: [code-review, security, quality]
dependencies: []
---

# Escape LLM output before passing to ReportLab `Paragraph()`

## Problem Statement

ReportLab's `Paragraph()` constructor parses its text argument as XML-like markup. LLM-generated strings (`content.opening`, `content.key_patterns`) are passed to `Paragraph()` in `build_provider_summary_pdf()` without any tag-stripping or escaping. If the LLM produces output containing XML-like tags (e.g., `<b>`, `<font color="red">`, `<a href=...>`) — whether through hallucination, indirect prompt injection from a RAG chunk, or model drift — ReportLab will either parse the tags unexpectedly (changing PDF formatting) or raise a `ValueError` on malformed markup (surfacing as a 500 error to the user).

This is a pre-existing issue, not introduced by this commit. The commit reduced the attack surface by removing `closing`, but two fields remain.

**Severity:** Low. Not exploitable beyond PDF rendering corruption or a 500 for a single user session. Not XSS, not data exfiltration.

## Findings

- `backend/app/services/pdf.py:530` — `story.append(Paragraph(content.opening, body_style))` — LLM output, no escaping
- `backend/app/services/pdf.py:539` — `story.append(Paragraph(content.key_patterns, body_style))` — LLM output, no escaping
- ReportLab parses `<b>text</b>`, `<font color="red">`, `<br/>` as real markup in `Paragraph()`
- An unbalanced `<` or `>` in LLM output will raise `ValueError: XML syntax error`
- The `_inline_md()` helper in the same file wraps text in ReportLab XML tags intentionally — but that path is for user-authored markdown, not LLM JSON fields
- `backend/app/llm/appointment_prompts.py:28–44` — `_sanitize_prompt_input()` already strips `<[^>]+>` tags for input going _into_ prompts. The same pattern applies in reverse for LLM output going into the PDF.
- This concern also applies in `build_cheatsheet_pdf()` if it passes LLM fields to `Paragraph()` directly.

## Proposed Solutions

### Option 1: Add `_strip_llm_tags()` helper in `pdf.py`

**Approach:** A one-liner helper that strips XML-like tags from LLM output before passing to `Paragraph()`:

```python
import re

def _strip_llm_tags(text: str) -> str:
    """Strip XML-like tags from LLM output to prevent ReportLab parse errors."""
    return re.sub(r"<[^>]+>", "", text).strip()
```

Apply at `pdf.py:530` and `pdf.py:539`:

```python
story.append(Paragraph(_strip_llm_tags(content.opening), body_style))
# ...
story.append(Paragraph(_strip_llm_tags(content.key_patterns), body_style))
```

**Pros:**

- Prevents ReportLab `ValueError` from malformed LLM markup
- Prevents unexpected formatting changes from LLM-generated tags
- Reuses the same `re.sub(r"<[^>]+>", "")` pattern already in `_sanitize_prompt_input()`
- Also handles `&` → `&amp;` if extended to `html.escape()` (see Option 2)

**Cons:**

- Strips intentional markdown-like formatting that the LLM might produce (but the prompt explicitly says "No markdown")

**Effort:** 30 minutes (including `build_cheatsheet_pdf()` audit)

**Risk:** Low

---

### Option 2: Use `html.escape()` before `Paragraph()`

**Approach:** Use Python's stdlib `html.escape()` which handles `<`, `>`, `&`, `"`, `'` → XML entities. ReportLab will then render them as literal characters.

```python
import html
story.append(Paragraph(html.escape(content.opening), body_style))
```

**Pros:**

- Also handles bare `&` (which is a valid ReportLab parse error trigger)
- stdlib, no new imports
  **Cons:**
- `html.escape()` also escapes `"` → `&quot;` and `'` → `&#x27;`, which ReportLab renders correctly but is slightly more aggressive than needed
- Cannot mix with intentional ReportLab markup (not an issue here since LLM output is plain text)

**Effort:** 30 minutes
**Risk:** Low

---

### Option 3: Accept the pre-existing risk; add a test

**Approach:** Don't sanitize. Add a test that passes a string with XML-like content and asserts the PDF still builds.

```python
def test_survives_llm_output_with_xml_tags(self, svc):
    result = svc.build_provider_summary_pdf(
        content=_provider_content(opening="Patient has <b>severe</b> hot flashes."),
        ...
    )
    assert result[:4] == b"%PDF"
```

This test would currently fail, documenting the issue rather than fixing it.

**Pros:** Documents the issue explicitly
**Cons:** The test fails; the risk remains
**Effort:** 15 minutes to write the failing test
**Risk:** None (test failure is informational)

## Recommended Action

Option 1 is the pragmatic fix. Option 2 is marginally more thorough. Given the prompt explicitly instructs the LLM to return no markdown, the real-world risk is very low — but the fix is cheap enough to be worth doing. Audit `build_cheatsheet_pdf()` at the same time.

## Technical Details

**Affected files:**

- `backend/app/services/pdf.py:530,539` — `build_provider_summary_pdf()`
- `backend/app/services/pdf.py` — also audit `build_cheatsheet_pdf()` for the same pattern

**Not affected:**

- `backend/app/services/pdf.py:534` — `narrative` arg is user-authored text that goes through `_inline_md()` intentionally
- `backend/app/services/pdf.py` — user-authored strings in other sections (concerns text) go through `sanitize_prompt_input()` before LLM calls, so the risk is at the LLM-output → PDF boundary

## Resources

- **Security review:** `security-sentinel` flagged as Finding 1 (pre-existing, Low severity)
- **Learnings:** `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md` — same `re.sub(r'<[^>]+>', '', text)` pattern for prompt input
- **Commit:** f4dc4b14 (this review)

## Acceptance Criteria

- [ ] `_strip_llm_tags()` helper added (or `html.escape()` used) for LLM fields passed to `Paragraph()`
- [ ] Applied to `content.opening` and `content.key_patterns` in `build_provider_summary_pdf()`
- [ ] Audit of `build_cheatsheet_pdf()` complete — same fix applied if needed
- [ ] Test added: PDF builds successfully when LLM output contains `<b>`, `&`, or `>` characters
- [ ] All tests pass

## Work Log

### 2026-04-08 - Identified in code review

**By:** Claude Code (ce-review)

**Actions:**

- Flagged by `security-sentinel` as a pre-existing, low-severity finding
- Confirmed by `learnings-researcher`: pattern for stripping tags exists in `_sanitize_prompt_input()`
- Removing `closing` in this commit reduced the surface by one field; `opening` and `key_patterns` remain
