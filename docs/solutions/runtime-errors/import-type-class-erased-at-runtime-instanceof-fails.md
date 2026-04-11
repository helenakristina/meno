---
title: "import type erases class at runtime — instanceof checks silently fail"
category: runtime-errors
date: 2026-04-11
tags:
  [
    typescript,
    svelte,
    error-handling,
    import-type,
    instanceof,
    appointment-prep,
  ]
components: [frontend, appointment-prep]
severity: p1
---

# `import type` Erases Class at Runtime — `instanceof` Checks Silently Fail

## Problem Symptom

All `catch` blocks in the appointment prep flow showed the generic fallback message
("Failed to save your selections. Please try again.") regardless of what the backend
actually returned. Backend 422/400 errors with meaningful `detail` fields were never
surfaced to the user.

No compile error. No runtime `ReferenceError`. Completely silent.

## Root Cause

`ApiError` was imported with `import type`:

```typescript
import type { ApiError } from "$lib/types";
```

TypeScript's `import type` is **erased entirely at compile time** — the identifier
does not exist at runtime. The catch blocks used it in a runtime check:

```typescript
} catch (e) {
    const msg =
        e instanceof Error && 'detail' in e
            ? (e as ApiError).detail          // cast is type-only — fine
            : 'Failed to save. Please try again.';
}
```

The workaround (`e instanceof Error && 'detail' in e`) was intended to guard the
cast, but it only passes when an error object happens to have a `detail` property
by coincidence. Because `ApiError` extends `Error` and `apiClient` throws instances
of it, the real fix is `e instanceof ApiError` — which requires `ApiError` to exist
as a runtime value, not a type alias.

## Why It's Tricky

- TypeScript does not warn when you use a `type`-imported name in a position that
  requires a runtime value (like the right-hand side of `as` cast or inside a
  function body that never actually calls `instanceof`).
- The `'detail' in e` fallback partially worked — if the thrown object happened to
  have `detail`, the message was extracted. So the bug was intermittent in testing
  and hard to reproduce reliably.
- The barrel re-export in `$lib/types/index.ts` used `export type { ApiError }`,
  which propagates the type-only restriction even if you write `import { ApiError }`
  from the barrel. Fix required importing directly from the source file.

## Solution

**1. Import as a value, directly from the source module:**

```typescript
// Before (erased at runtime):
import type { ApiError } from "$lib/types";

// After (value import from source — not the barrel that re-exports as type):
import { ApiError } from "$lib/types/api";
```

Check the barrel (`$lib/types/index.ts`) — if it re-exports as `export type { ApiError }`,
importing from the barrel will still erase the class. Import from the module that
defines the class directly.

**2. Use `instanceof` directly:**

```typescript
} catch (e) {
    const msg = e instanceof ApiError ? e.detail : 'Failed to save. Please try again.';
}
```

No cast needed — TypeScript narrows `e` to `ApiError` inside the truthy branch.

## Files Fixed

- `frontend/src/routes/(app)/appointment-prep/+page.svelte`
- `frontend/src/routes/(app)/appointment-prep/Step3Qualitative.svelte`
- `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte`

## Prevention

**When writing `catch` blocks that extract typed error properties:**

1. Check whether the error class is imported as `import type` or `import`.
2. If `instanceof` is used anywhere in the catch block, the import must be a value import.
3. Check the barrel — `export type { Foo }` from a barrel forces type-only regardless
   of how you import at the consumer.

**Heuristic:** If your catch block looks like `(e as SomeError).property`, search for
how `SomeError` is imported. A `type` import means the cast is documentation-only and
the runtime check will silently fail.

## Related

- `docs/solutions/patterns/svelte5-lifecycle-patterns.md` — other Svelte 5 gotchas
  found in the same appointment prep review pass
- Commit: `e690800` (todo 107 resolution)
