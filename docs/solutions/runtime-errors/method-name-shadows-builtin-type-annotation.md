---
title: Method name shadows built-in type — TypeError in class body annotations
category: runtime-errors
date: 2026-03-18
tags:
  - python
  - pydantic
  - type-annotations
  - fastapi
  - repositories
components:
  - backend/app/repositories
  - backend/app/services
---

## Problem

Defining a method named `list` (or any built-in name) inside a class causes a `TypeError: 'function' object is not subscriptable` when Python evaluates subsequent return type annotations that use the shadowed name.

```python
class MedicationRepository:

    async def list(self, user_id: str) -> list[MedicationResponse]:  # ← defines `list`
        ...

    async def list_current(self, user_id: str) -> list[MedicationResponse]:
        #                                          ^^^^ Python now resolves `list`
        #                                          as the method above, not the built-in
        ...
```

**Symptom:** `TypeError: 'function' object is not subscriptable` at class definition time (import), not at call time.

## Root Cause

When Python parses a class body, all method definitions are executed sequentially. After `def list(...)` runs, the name `list` in the class namespace now refers to the function object. When the next method's return annotation `-> list[MedicationResponse]` is evaluated eagerly, Python looks up `list` in the class scope, finds the function, and fails when it tries to subscript it (`function[MedicationResponse]`).

## Solution

Two complementary fixes — use both:

### 1. Add `from __future__ import annotations` at the top of the file

```python
from __future__ import annotations  # ← defers all annotation evaluation to strings
```

This makes Python treat all annotations as string literals, bypassing the eager lookup entirely. No class-body scope pollution matters at parse time.

### 2. Rename the conflicting method

Rename `list` to `list_all` (or another non-shadowing name) to be explicit and avoid confusion:

```python
async def list_all(self, user_id: str) -> list[MedicationResponse]:
    ...
```

Update all callers (routes, services, ABC base class) accordingly.

## Files Changed

```
backend/app/repositories/medication_repository.py
backend/app/services/medication.py
backend/app/services/medication_base.py
```

## Prevention

- **Never name a method after a Python built-in** (`list`, `dict`, `set`, `type`, `id`, `input`, `filter`, `map`, `zip`, etc.). Linters catch some of these (`E741` for `l`, `O`, `I`), but not method names matching built-ins.
- **Add `from __future__ import annotations` to all new repository/service files** as a default. It defers annotation evaluation, eliminates forward-reference headaches, and costs nothing at runtime.
- **Use descriptive method names**: `list_all`, `list_current`, `list_active`, `list_by_date` — more expressive than `list` and avoids the collision.

## Related

- Python docs: [PEP 563 — Postponed Evaluation of Annotations](https://peps.python.org/pep-0563/)
- Applies to any file with a class that defines a method shadowing a built-in used in type hints within the same class body.
