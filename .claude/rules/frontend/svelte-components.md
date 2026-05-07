---
paths: [frontend/src/**/*.svelte]
---

# Svelte Component Rules

## Svelte 5 — Breaking Changes From Svelte 4

These are not style preferences. Svelte 4 syntax is wrong in this codebase.

| Svelte 4 (wrong)                     | Svelte 5 (correct)                  |
| ------------------------------------ | ----------------------------------- |
| `export let foo`                     | `let { foo } = $props<Props>()`     |
| `on:click={handler}`                 | `onclick={handler}`                 |
| `<slot />`                           | `{@render children()}`              |
| `import { page } from '$app/stores'` | `import { page } from '$app/state'` |

## Props

Always typed, always via `$props<Props>()`, always with defaults for optional props:

```svelte
<script lang="ts">
  interface Props {
    label: string;
    variant?: 'primary' | 'secondary' | 'danger';
    disabled?: boolean;
    onclick?: () => void | Promise<void>;
  }
  let { label, variant = 'primary', disabled = false, onclick } = $props<Props>();
</script>
```

## State: Runes vs Stores

| Use                                       | When                                        |
| ----------------------------------------- | ------------------------------------------- |
| `$state`, `$derived`, `$effect`           | Inside `.svelte` files only                 |
| `writable`, `derived` from `svelte/store` | Inside `.ts` files (not compiled by Svelte) |

Do not mix runes and stores in the same file.

## $effect — Last Resort, Not Default

`$effect` re-runs whenever dependencies change. Overuse causes infinite loops
and makes data flow hard to reason about.

| You want to...         | Wrong                                    | Right                               |
| ---------------------- | ---------------------------------------- | ----------------------------------- |
| Fetch on mount         | `$effect(() => fetchData())`             | `onMount(() => fetchData())`        |
| Compute from state     | `$effect(() => { doubled = count * 2 })` | `let doubled = $derived(count * 2)` |
| Respond to user action | `$effect` watching a flag                | Event handler                       |
| Sync state to state    | `$effect(() => { b = a + 1 })`           | `let b = $derived(a + 1)`           |

Use `$effect` only for syncing with external systems (DOM APIs, third-party
libraries) where the sync must re-run when reactive dependencies change.

## Async Data Pattern

Every component that fetches data must follow this shape:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';

  let data = $state<MyData | null>(null);
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  async function fetchData() {
    isLoading = true;
    error = null;
    try {
      data = await apiClient.get('/api/endpoint');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load data';
    } finally {
      isLoading = false;
    }
  }

  onMount(fetchData);
</script>

{#if isLoading}
  <LoadingSpinner />
{:else if error}
  <div role="alert">{error}</div>
{:else if data}
  <!-- render -->
{:else}
  <p>No data</p>
{/if}
```

Never fetch without a loading state. Never fetch without error handling.

## Accessibility (WCAG 2.1 AA — Non-Negotiable)

- Semantic HTML: `<nav>`, `<main>`, `<section>`, `<button>` — not `<div>` with click handlers
- Every `<input>` has a `<label for="id">`. Icon-only buttons have `aria-label`
- Never `outline: none`. Use `focus-visible` with a visible ring
- Touch targets: 44×44px minimum on all interactive elements
- Color contrast: 4.5:1 normal text, 3:1 large text (18px+)
- Dynamic content: `role="alert"` + `aria-live="polite"` on messages that appear
- Loading states: `aria-busy="true"` on container, `role="status"` on spinner
- All interactive elements reachable via Tab, activated via Enter/Space

## Forms: Zod + Superforms

- Validate server-side in `+page.server.ts` with Superforms
- Client-side validation is UX enhancement only, not security
- One Zod schema per form in `src/lib/schemas/`
- **Bind inputs directly to `$formData`** — not a separate local state variable

```svelte
<!-- YES — single source of truth -->
<textarea bind:value={$formData.message} />

<!-- NO — local state silently desynchronizes; form submits empty data -->
<script>let message = $state('');</script>
<textarea bind:value={message} />
```

## Security

- Never `{@html userContent}` — always `{@html DOMPurify.sanitize(content)}`
- No `VITE_` prefixed secrets — only the backend holds API keys

## Responsive Design

Mobile-first. Test at 375px, 667px, 768px, 1440px. No horizontal overflow.
Start with mobile layout, add `sm:`, `md:`, `lg:` breakpoints.
Never use fixed widths (`w-[1200px]`). Minimum font size 14px mobile, 16px tablet+.
