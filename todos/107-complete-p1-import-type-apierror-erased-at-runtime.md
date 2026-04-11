---
status: complete
priority: p1
issue_id: "107"
tags: [code-review, frontend, appointment-prep, typescript, error-handling, bug]
---

# `import type { ApiError }` erased at runtime — all catch blocks use generic message

## Problem Statement

`ApiError` is imported with `import type` in three appointment prep components, which means TypeScript erases it at compile time. It does not exist at runtime. The `instanceof Error` check combined with `'detail' in e` is being used as a stand-in type guard, but because `ApiError` is not available at runtime, the cast `(e as ApiError).detail` is never the primary evaluation path — it only runs when some arbitrary error happens to have a `detail` property.

In practice: every `catch` block in the appointment prep flow falls through to the generic error message, regardless of whether the backend returned a meaningful error. Users always see "Failed to save your selections. Please try again." instead of the actual API error detail.

## Findings

- **File:** `frontend/src/routes/(app)/appointment-prep/+page.svelte` line 12

  ```ts
  import type { ApiError } from "$lib/types";
  ```

  Used at line 85–87:

  ```ts
  e instanceof Error && "detail" in e
    ? (e as ApiError).detail
    : "Failed to save your selections. Please try again.";
  ```

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3Qualitative.svelte` line 4
  Same import, same pattern at lines 43–45 and 68–70.

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3Prioritize.svelte` line 5
  Same import, same pattern at lines 119–121.

- **Root cause:** `import type` strips the import entirely. `instanceof ApiError` would fail at runtime with `ReferenceError: ApiError is not defined`. The workaround `'detail' in e` can only access `detail` if `e` is an object with that property — which depends on how `apiClient` throws.

## Proposed Solutions

### Option A: Change to value import and use `instanceof ApiError` (Recommended)

Check how `ApiError` is defined in `$lib/types` — if it's a class, import it as a value:

```ts
import { ApiError } from '$lib/types';
// ...
} catch (e) {
    const msg = e instanceof ApiError ? e.detail : 'Failed to save your selections. Please try again.';
    state.error = msg;
}
```

- Effort: XS | Risk: Low (need to verify ApiError is exported as a class, not just a type/interface)

### Option B: Use the `'detail' in e` guard correctly (if ApiError is an interface)

If `ApiError` is a TypeScript interface (not a class), it cannot be used in `instanceof`. Use a proper type guard:

```ts
function isApiError(e: unknown): e is { detail: string } {
    return typeof e === 'object' && e !== null && 'detail' in e && typeof (e as any).detail === 'string';
}
// ...
} catch (e) {
    const msg = isApiError(e) ? e.detail : 'Failed to save your selections. Please try again.';
}
```

- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] When the backend returns a 422 or 400 with a `detail` field, the error message shown to the user is the backend's message, not the generic fallback
- [ ] All three files use a consistent error extraction pattern
- [ ] No `import type` for `ApiError` at sites that use it in a runtime check

## Work Log

- 2026-04-11: Found during code review of commits ef9745f/13f72a6 by TypeScript reviewer agent
