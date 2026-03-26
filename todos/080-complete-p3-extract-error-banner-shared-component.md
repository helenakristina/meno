---
status: ready
priority: p3
issue_id: "080"
tags: [code-review, frontend, design-system, refactor, pr-10]
dependencies: []
---

# Extract error banner into ErrorBanner.svelte shared component (15 repetitions across 11 files)

## Problem Statement

The danger/error banner pattern (`rounded-xl border border-danger-light bg-danger-light ... text-sm text-danger-dark`) is repeated 15 times across 11 files with minor radius/padding inconsistencies (`rounded-xl` vs `rounded-lg` vs `rounded-md`, `px-5 py-4` vs `px-4 py-3` vs `p-4`). This is the most repeated visual pattern exposed by the design system migration.

## Findings

- ~15 occurrences of the error/danger banner pattern across: `dashboard`, `log`, `ask`, `ask/history`, `appointment-prep/history`, `providers`, `period`, `medications/*`, `export`, `settings`
- Inconsistent sizing: 3 different padding variants, 3 different border-radius values
- `ErrorBanner.svelte` does not yet exist in `$lib/components/shared/`
- Identified by code-simplicity-reviewer

## Proposed Solutions

### Option 1: ErrorBanner.svelte shared component (Recommended)

Create `frontend/src/lib/components/shared/ErrorBanner.svelte`:

```svelte
<script lang="ts">
  let { message, onRetry }: { message: string; onRetry?: () => void } = $props();
</script>

<div class="rounded-lg border border-danger-light bg-danger-light px-4 py-3 text-sm text-danger-dark" role="alert">
  <p>{message}</p>
  {#if onRetry}
    <button onclick={onRetry} class="mt-2 font-medium underline hover:no-underline">
      Try again
    </button>
  {/if}
</div>
```

Then replace the 15 repetitions with `<ErrorBanner message={error} onRetry={fetchData} />`.

**Pros:** Single place to adjust error banner styling, consistent appearance
**Effort:** Medium (1–2 hours)
**Risk:** Low

## Recommended Action

Option 1. Good follow-up to this PR — don't add to the current PR scope.

## Acceptance Criteria

- [ ] `ErrorBanner.svelte` exists in `$lib/components/shared/`
- [ ] At least dashboard, log, ask, and providers pages use it
- [ ] All error banners are consistently styled (same padding, same radius)
- [ ] `onRetry` prop is optional for cases without a retry action

## Work Log

- 2026-03-25: Identified by code-simplicity-reviewer in PR #10 review
