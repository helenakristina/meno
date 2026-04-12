---
status: complete
priority: p2
issue_id: "120"
tags: [code-review, architecture, frontend, duplication]
---

# Nav header triplicated across about/privacy/contact — extract shared shell

## Problem Statement

The 12-line nav header block and its surrounding `min-h-screen bg-white` wrapper are byte-for-byte identical in all three new public pages. The logo import (`import logo from '$lib/assets/logo.png'`) is also duplicated in each `<script>` block.

Any change to the nav (link target, logo path, styling, back arrow text) must be made in three places with no guardrail against drift. A fourth public page (e.g. terms, FAQ) would copy-paste again.

## Findings

- `frontend/src/routes/about/+page.svelte:1-25` — nav block + logo import
- `frontend/src/routes/privacy/+page.svelte:1-25` — identical
- `frontend/src/routes/contact/+page.svelte:1-25` — identical
- **Flagged by:** architecture-strategist, kieran-typescript-reviewer, code-simplicity-reviewer (all three independently)

## Proposed Solutions

### Option A: `PublicPageShell.svelte` component (recommended)

Create `frontend/src/lib/components/shared/PublicPageShell.svelte`:

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import logo from '$lib/assets/logo.png';

  let { children }: { children: Snippet } = $props();
</script>

<div class="min-h-screen bg-white">
  <header class="border-b border-neutral-200 px-6 py-4">
    <div class="mx-auto flex max-w-3xl items-center justify-between">
      <a href="/" class="flex items-center gap-2.5">
        <img src={logo} alt="" class="h-8 w-8 rounded-lg" aria-hidden="true" />
        <span class="text-xl font-bold tracking-tight text-neutral-800">Meno</span>
      </a>
      <a href="/" class="text-sm font-medium text-neutral-500 transition-colors hover:text-neutral-700">
        &larr; Back
      </a>
    </div>
  </header>
  <div class="mx-auto max-w-3xl px-6 py-16">
    <div class="max-w-[65ch]">
      {@render children()}
    </div>
  </div>
</div>
```

Each page becomes its `<svelte:head>` plus content only. Logo import and script blocks can be removed from about and privacy entirely.

**Pros:** Idiomatic Svelte 5 (`{@render children()}`), consistent with existing SharedError pattern, -42 lines across pages  
**Cons:** One new file  
**Effort:** Small  
**Risk:** None

### Option B: `(public)` route group with `+layout.svelte`

Create `src/routes/(public)/+layout.svelte` and move the three pages under it. The layout owns the nav.

**Pros:** Idiomatic SvelteKit (mirrors `(auth)` and `(app)` groups)  
**Cons:** Requires moving three files, slightly more restructuring  
**Effort:** Small-Medium  
**Risk:** Low — SvelteKit handles route group moves transparently, URLs unchanged

## Acceptance Criteria

- [ ] Nav header defined in exactly one place
- [ ] Logo imported in exactly one place
- [ ] All three pages (`/about`, `/privacy`, `/contact`) render identically to current
- [ ] A fourth public page can reuse the shell without copy-paste

## Work Log

- 2026-04-11: Identified by PR #22 code review (architecture-strategist, typescript-reviewer, simplicity-reviewer)
