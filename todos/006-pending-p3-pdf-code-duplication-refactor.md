---
name: Refactor PDF Code Duplication
status: complete
priority: p3
tags: [code-review, refactor, code-quality]
dependencies: []
---

## Problem Statement

`build_provider_summary_pdf` and `build_cheatsheet_pdf` in `pdf.py` share ~80% identical boilerplate code, violating DRY.

## Findings

**From:** code-simplicity-reviewer

**Location:** `backend/app/services/pdf.py` lines 438-644, 646-829

**Duplicated patterns:**

- Buffer setup (BytesIO, SimpleDocTemplate)
- Style definitions (15+ lines repeated)
- Page footer function (defined 3+ times)
- Table styling patterns

**Estimated savings:** ~200 lines

## Proposed Solutions

### Option A: Extract Common Helpers (Recommended)

**Effort:** Medium

```python
def _create_base_styles(prefix: str) -> dict:
    """Return common styles with prefixed names."""
    return {
        "title": ParagraphStyle(f"{prefix}Title", ...),
        "meta": ParagraphStyle(f"{prefix}Meta", ...),
        # ... etc
    }

def _build_pdf(story: list, footer_func=None) -> bytes:
    """Common PDF building logic."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, ...)
    doc.build(story, onFirstPage=footer_func, onLaterPages=footer_func)
    return buffer.getvalue()

# Module-level shared footer
def _page_footer(canvas, doc):
    """Single shared footer implementation."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_NEUTRAL_LIGHT)
    canvas.drawRightString(letter[0] - 0.9*inch, 0.45*inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()
```

### Option B: Accept Current Duplication

**Risk:** Higher maintenance burden, inconsistent changes.

## Recommended Action

Implement Option A as post-merge cleanup.

## Technical Details

**Affected file:** `backend/app/services/pdf.py`

**Considerations:**

- Maintain backward compatibility
- Ensure styles remain customizable per PDF type
- Test all PDF generation paths

## Acceptance Criteria

- [ ] Common PDF building logic extracted
- [ ] Shared footer function created
- [ ] Style creation helper implemented
- [ ] All existing PDF generation still works
- [ ] Tests pass
- [ ] ~200 lines removed

## Work Log

| Date       | Action                         | Result  |
| ---------- | ------------------------------ | ------- |
| 2026-03-31 | Created from simplicity review | Pending |
