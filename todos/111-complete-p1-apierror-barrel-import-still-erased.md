---
status: complete
priority: p1
issue_id: "111"
tags: [code-review, frontend, typescript, appointment-prep, error-handling, bug]
---

# `import { ApiError } from '$lib/types'` still erased at runtime in Step3Prioritize and Step3Qualitative

## Problem Statement

Todo 107 fixed the `import type { ApiError }` erasure in `+page.svelte` by importing directly from `'$lib/types/api'`. However the same fix was applied incorrectly to `Step3Prioritize.svelte` and `Step3Qualitative.svelte` — both now import from the barrel `'$lib/types'` instead of the source module.

The barrel at `$lib/types/index.ts` uses `export type { ApiError }`, which forces type-only semantics on any consumer regardless of how they import. Both step components still have `ApiError` erased at compile time; every `e instanceof ApiError` check evaluates to `false` at runtime, and backend error details are still never surfaced to the user.

## Findings

- **Discovered by:** TypeScript reviewer + security sentinel during review of commit e690800
- **Files:** `Step3Prioritize.svelte:5`, `Step3Qualitative.svelte:4`
- **Current (broken):**
  ```ts
  import { ApiError } from '$lib/types';   // barrel uses export type — still erased
  ```
- **+page.svelte (correct):**
  ```ts
  import { ApiError } from '$lib/types/api';   // direct source import — survives compile
  ```

## Proposed Solution

Change both files to import directly from the source module, matching the fix in `+page.svelte`:

```ts
import { ApiError } from '$lib/types/api';
```

- Effort: XS | Risk: None

## Acceptance Criteria
- [ ] `Step3Prioritize.svelte` imports `ApiError` from `'$lib/types/api'`
- [ ] `Step3Qualitative.svelte` imports `ApiError` from `'$lib/types/api'`
- [ ] Backend error details (e.g. 422 `detail`) are surfaced in catch blocks in both files

## Work Log
- 2026-04-11: Found during code review of commit e690800 by TypeScript + security reviewers
