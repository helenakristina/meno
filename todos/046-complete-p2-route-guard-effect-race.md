---
status: complete
priority: p2
issue_id: "046"
tags: [code-review, frontend, svelte5, medications, ux, pr-2]
dependencies: [043]
---

# Medications route guard via `$effect` + `goto` races settings load

## Problem Statement

The `/medications` page uses `$effect` to redirect when `mht_tracking_enabled=false`. But `$userSettings` is populated asynchronously by the layout's `onMount` — between page mount and the settings response arriving, the guard is inert. The medications list may load and render briefly before the redirect fires.

## Findings

- `frontend/src/routes/(app)/medications/+page.svelte` lines 25–30
- Guard: `$effect(() => { if ($userSettings !== null && !$userSettings.mht_tracking_enabled) goto('/settings'); })`
- `$userSettings` is null on first render → guard doesn't run → medications fetch races with settings fetch
- If medications load first, user briefly sees the list before redirect
- `$effect` + `goto` during rendering triggers Svelte lifecycle warnings
- Client-side guard is also not a security control (identified by security-sentinel as separate issue — write endpoints need backend enforcement)
- Identified by TypeScript reviewer

## Proposed Solutions

### Option 1: Move guard to `+page.ts` load function (Recommended)

```ts
// frontend/src/routes/(app)/medications/+page.ts
import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ parent }) => {
  const { userSettings } = await parent();
  if (!userSettings?.mht_tracking_enabled) {
    redirect(302, '/settings');
  }
};
```

The layout's `load` function must expose `userSettings` for `parent()` to work.

**Pros:** Blocks rendering entirely until settings are known, no flash, correct SvelteKit idiom
**Effort:** Small
**Risk:** Low

### Option 2: Show loading spinner until settings resolve, then check

Keep the `$effect` but add an explicit loading state:
```svelte
{#if $userSettings === null}
  <!-- loading -->
{:else if !$userSettings.mht_tracking_enabled}
  <!-- redirect handled by $effect -->
{:else}
  <!-- medications list -->
{/if}
```

**Cons:** Still client-side, flash avoided by hiding content — but navigating to the page is still allowed by the router
**Effort:** Small

## Recommended Action

Option 1 — `+page.ts` load is the idiomatic SvelteKit way to guard routes. Option 2 is acceptable if Option 1 requires larger layout refactoring.

## Technical Details

**Affected files:**
- `frontend/src/routes/(app)/medications/+page.ts` (create)
- `frontend/src/routes/(app)/medications/+page.svelte` lines 25–30 (remove `$effect` guard)
- `frontend/src/routes/(app)/+layout.ts` (may need to expose `userSettings` from server load)

## Acceptance Criteria

- [ ] Navigating to `/medications` with `mht_tracking_enabled=false` redirects instantly with no flash
- [ ] No Svelte lifecycle warnings from `goto` during rendering

## Work Log

- 2026-03-18: Identified by TypeScript reviewer in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
