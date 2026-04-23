---
status: complete
priority: p3
issue_id: "131"
tags: [code-review, python, quality, context-builder, test-quality]
---

# PR #25 batch: minor code quality and test fixes

## Problem Statement

A set of small, independent improvements identified during PR #25 review. None blocks merge.

---

### 1. `parts` single-element list in `ContextBuilder.build` is confusing — `context_builder.py:87–94`

```python
parts = [f"  - {name} {dose} ({method})"]
if med.frequency:
    parts[0] += ...
med_lines.extend(parts)
```

`parts` is always a one-element list. `parts[0] +=` looks like it could grow; `extend` implies multiple items. Carried over from old PromptService code. Replace with a local `line` variable and `med_lines.append(line)`.

---

### 2. `TYPE_CHECKING`-only import for `MedicationContext` adds fragility — `context_builder.py:14–16`

`MedicationContext` is in a leaf model module with no circular import risk. The `TYPE_CHECKING` guard is a pattern for breaking circular imports; it doesn't apply here. `from __future__ import annotations` covers the runtime behavior, but the guard adds confusion. Move to a regular import.

---

### 3. `pytest.raises(Exception)` too broad — `test_ask_meno_service.py:563`

```python
with pytest.raises(Exception):
    await svc.ask(USER_ID, "What causes hot flashes?")
```

The test is named `test_malformed_json_from_llm_raises_exception` and PR #25 explicitly surfaced `DatabaseError` on JSON parse failure. Assert the specific type:

```python
with pytest.raises(DatabaseError, match="Failed to parse structured LLM response"):
```

---

### 4. Weak `or` assertion in newline injection test is always True — `test_context_builder.py:253–256`

```python
assert (
    "\n" not in result or "User context:" in result
)  # newline not in med field
```

`"User context:"` is always in result, so the `or` makes the left side irrelevant. The meaningful assertion (`assert "SYSTEM: override" not in result`) is already present on line 256. Remove the redundant `or` assertion.

---

### 5. `len(chunks)` vs `len(source_lines)` for `source_count` — `context_builder.py:54`

`source_count = len(chunks)` and `source_lines` always has one entry per chunk, so they're equivalent. Using `len(source_lines)` is more locally consistent — the count reflects what was actually rendered.

---

### 6. `ContextBuilder` class with one `@staticmethod` — `context_builder.py`

Every other module in `app/utils/` uses module-level functions (`dates.py`, `stats.py`, `sanitize.py`, `conversations.py`). `ContextBuilder` is a stateless class wrapping one pure function. Convert to `def build_context_block(...)` at module level. `PromptService` can be similarly converted once `ContextBuilder` is resolved. See also: architecture-strategist P3.

---

### 7. `TestParityWithPromptService` class name is stale — `test_context_builder.py:68`

The inline PromptService implementation it was verifying parity against no longer exists. Rename to `TestCoreFields` or `TestUserContextBlock`.

## Proposed Solution

Address each item individually. All are trivial edits.

**Effort:** Small (total for all 7)  
**Risk:** None

## Acceptance Criteria

- [ ] `parts` list replaced with `line` variable in medication loop
- [ ] `MedicationContext` imported unconditionally (no `TYPE_CHECKING` guard)
- [ ] `pytest.raises(DatabaseError, match=...)` in `test_malformed_json_from_llm_raises_exception`
- [ ] Redundant `or` assertion in newline injection test removed
- [ ] `source_count = len(source_lines)` (or kept as `len(chunks)` with a comment justifying the choice)
- [ ] `ContextBuilder` converted to module-level function (or class kept with a comment explaining intent)
- [ ] `TestParityWithPromptService` renamed

## Work Log

- 2026-04-15: Identified by PR #25 code review (kieran-python-reviewer, architecture-strategist, code-simplicity-reviewer)
