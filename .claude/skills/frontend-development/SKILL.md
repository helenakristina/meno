---
name: frontend-development
description: >
  Use when writing, modifying, or reviewing any frontend code (SvelteKit routes,
  components, stores, API calls, forms, tests). Enforces this project's patterns:
  Svelte 5 runes, Zod + Superforms validation, typed API client, accessibility
  (WCAG 2.1 AA), and mobile-first responsive design.
when_to_use: >
  Any frontend task: new pages, components, forms, API integration, state management,
  testing, or code review in the frontend/ directory.
version: 1.0.0
languages: [typescript, svelte]
---

# Frontend Development

## Stack

SvelteKit 2.x + Svelte 5 (runes) + TypeScript + Tailwind CSS + shadcn-svelte.
Zod for validation, Superforms for form handling, Supabase for auth.
Backend is FastAPI — frontend calls it via typed API client (browser) or
fetch + locals.token (server actions).

---

## Type Safety

**No implicit `any`. Ever.**

### Types live in `src/lib/types/`

One domain = one file (`chat.ts`, `symptoms.ts`, etc.). Export from `index.ts`.
Use `interface` for object types. Include state types alongside domain types.

### Component props are always typed

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

Always use `$props<Type>()`. Provide defaults for optional props.

### API endpoints are typed via `ApiEndpoints` map

All API endpoints must be defined in `src/lib/types/api.ts` in the `ApiEndpoints`
interface. The typed API client validates paths, request bodies, and response types
at compile time.

When adding a new endpoint: add it to `ApiEndpoints` first, then the client
automatically gets type checking. Use the escape hatch (`apiClient.post<MyType>(...)`)
only for external APIs.

### `ApiError` is a class, not an interface

`ApiError` must be a class extending `Error` so that `instanceof` checks work
at runtime. Never use interface + object literal for errors — `instanceof` will
always fail.

---

## Forms: Zod + Superforms

### Rules

- **Always validate server-side** with Superforms in `+page.server.ts`
- Client-side validation is UX enhancement, not security
- One Zod schema per form in `src/lib/schemas/`
- Export both the schema and its inferred type

### Form data binding: single source of truth

**Bind inputs directly to `$formData`, not a separate local state variable.**

```svelte
<!-- YES — single source of truth -->
<textarea bind:value={$formData.message} />

<!-- NO — creates silent desync, form submits empty data -->
<script>
  let message = $state('');  // This is NOT what gets submitted
</script>
<textarea bind:value={message} />
```

If you need local state for UX features (clearing after submit, character count),
sync it back to `$formData` via `$effect`.

### Accessibility in forms

Every form input needs: `<label for="id">`, `aria-invalid` when errors exist,
`aria-describedby` linking to the error message element, and `role="alert"` on
error messages.

---

## Server Actions vs Browser Client

**This is a critical distinction. Getting it wrong causes silent auth failures.**

| Context                        | Use This                            | Token Source                                |
| ------------------------------ | ----------------------------------- | ------------------------------------------- |
| `.svelte` components (browser) | `apiClient` from `$lib/api/client`  | `supabase.auth.getSession()`                |
| `+page.server.ts` actions      | `fetch()` or `serverFetch()` helper | `locals.token` (set in `+layout.server.ts`) |

**Never import `apiClient` in `+page.server.ts`.** It calls
`supabase.auth.getSession()` which only exists in the browser.

Server actions must: check `locals.user` and `locals.token`, use `fetch()` with
`Authorization: Bearer ${locals.token}`, and use the `SECRET_API_BASE_URL`
environment variable (not the public VITE one).

---

## State Management

### The runes vs stores boundary

| File type             | Use this                                  | Why                                      |
| --------------------- | ----------------------------------------- | ---------------------------------------- |
| `.svelte`             | `$state`, `$derived`, `$effect`           | Compiled by Svelte                       |
| `.ts` (plain modules) | `writable`, `derived` from `svelte/store` | Not compiled by Svelte, runes don't work |

**Do not mix runes and stores in the same file.**

### Decision guide

- **Only used in this component?** → `$state` in the `.svelte` file
- **Shared across pages/components?** → Store in a `.ts` file with `writable`
- **Computed from other state?** → `$derived` in `.svelte`, `derived` in `.ts`
- **Run once on mount (fetch data, set up subscriptions)?** → `onMount` in `.svelte`

### `$effect` — Almost never the right tool

**The Svelte team explicitly warns against overusing `$effect`.** It should be a
last resort, not a default. Claude tends to reach for `$effect` for everything —
resist this.

**Use `$effect` ONLY for:** synchronizing with external systems (DOM APIs, third-party
libraries, browser APIs) where the sync must re-run when reactive dependencies change.

**Do NOT use `$effect` for:**

| You want to...                        | Wrong                                     | Right                               |
| ------------------------------------- | ----------------------------------------- | ----------------------------------- |
| Fetch data on mount                   | `$effect(() => { fetchData(); })`         | `onMount(() => { fetchData(); })`   |
| Compute a value from state            | `$effect(() => { doubled = count * 2; })` | `let doubled = $derived(count * 2)` |
| Respond to a user action              | `$effect` watching a flag                 | Event handler / callback            |
| Update state when other state changes | `$effect(() => { b = a + 1; })`           | `let b = $derived(a + 1)`           |

**Why this matters:** `$effect` re-runs whenever its dependencies change. This
causes infinite loops when the effect itself updates state that it reads, triggers
unnecessary refetches, and makes data flow harder to reason about. `onMount` runs
once. `$derived` is declarative and doesn't cause cycles.

```svelte
<!-- NO — $effect refires if dependencies change, potential infinite loop -->
<script lang="ts">
  import { onMount } from 'svelte';

  let data = $state(null);

  $effect(() => {
    fetchData();  // Runs again if anything reactive in here changes
  });
</script>

<!-- YES — onMount runs once, clean and predictable -->
<script lang="ts">
  import { onMount } from 'svelte';

  let data = $state(null);

  onMount(() => {
    fetchData();  // Runs once on mount, done
  });
</script>
```

---

## Error Handling

Three levels, don't mix them:

| Level     | Mechanism                             | Use for                                  |
| --------- | ------------------------------------- | ---------------------------------------- |
| Route     | SvelteKit `+error.svelte`             | Errors in `+page.server.ts` load/actions |
| Component | `try/catch` + `$state` error variable | Async operations within components       |
| Form      | Superforms `$errors`                  | Validation errors from Zod schemas       |

### The standard async pattern

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

  onMount(() => {
    fetchData();
  });
</script>

{#if isLoading}
  <LoadingSpinner />
{:else if error}
  <div role="alert">{error}</div>
{:else if data}
  <!-- render data -->
{:else}
  <p>No data</p>
{/if}
```

Never fetch without a loading state. Never fetch without error handling.

---

## Component Organization

### Folder structure

```
src/lib/
├── components/
│   ├── ui/          ← shadcn-svelte primitives
│   ├── forms/       ← form components
│   ├── layouts/     ← layout components
│   └── shared/      ← reusable (Spinner, ErrorMessage, etc.)
├── api/             ← client.ts (browser), server.ts (server-side helper)
├── stores/          ← shared state (.ts files with writable/derived)
├── types/           ← domain types, API types, exported from index.ts
├── schemas/         ← Zod schemas for forms
└── utils/           ← pure functions
```

### Component template (Svelte 5)

Every component must have: `lang="ts"` on script tag, typed props via
`$props<Props>()`, JSDoc description, and no global styles in `<style>`.

---

## Multi-Step Flows (Wizards)

Use the orchestrator + steps pattern. Reference implementation:
`frontend/src/routes/(app)/appointment-prep/`

### Rules

- **Single orchestrator** owns all flow state in one typed `$state` object
- **Step numbers** are literal unions (`1 | 2 | 3 | 4 | 5`), not arbitrary numbers
- **Steps are dumb** — they receive data via props, call `onNext()` when done
- **Back-navigation** never clears data, never validates
- **Each step** handles its own loading/error UI with retry buttons
- **Retry at step level** — never force backward navigation on failure
- **Persist to sessionStorage** for flows with expensive operations (LLM calls)
- **Progress indicator** with ARIA attributes (`role="progressbar"`, `aria-valuenow`)

**Anti-pattern:** Distributing state across multiple stores or letting steps own
their own state. This makes persistence, reset, and back-navigation painful.

---

## Accessibility (WCAG 2.1 AA)

These are not optional. Every component, every time.

### Non-negotiable rules

- **Semantic HTML:** Use `<nav>`, `<main>`, `<section>`, `<button>` — not `<div>` with click handlers
- **Labels:** Every `<input>` has a `<label for="id">`. Icon-only buttons have `aria-label`
- **Focus indicators:** Never `outline: none`. Use `focus-visible` with visible ring
- **Touch targets:** 44×44px minimum on all interactive elements
- **Color contrast:** 4.5:1 for normal text, 3:1 for large text (18px+)
- **Dynamic content:** `role="alert"` + `aria-live="polite"` on messages that appear/change
- **Expandable content:** `aria-expanded` + `aria-controls`
- **Loading states:** `aria-busy="true"` on container, `role="status"` on spinner
- **Keyboard navigation:** All interactive elements reachable via Tab, activated via Enter/Space

---

## Responsive Design (Mobile-First)

Test at **375px, 667px, 768px, 1440px**. No horizontal overflow at any width.

### Rules

- Start with mobile layout, add breakpoints for larger screens (`sm:`, `md:`, `lg:`)
- Use `flex flex-col sm:flex-row` for layouts that stack on mobile
- Never use fixed widths (`w-[1200px]`). Use `w-full max-w-full`
- Container padding: `px-4 sm:px-6 lg:px-8`
- Minimum font size: 14px on mobile (`text-sm`), 16px on tablet+

---

## Transitions & Animations

### When to use

Svelte transitions (`in:`, `out:`) for elements entering/leaving the DOM:
cards added/removed, modals, alerts, loading→content swaps.

**Do NOT use Svelte transitions for:** hover effects (CSS), spinners (CSS rotation),
animated values (`$derived` + CSS transitions).

### Duration guidelines

- Quick feedback (dismiss, success): **150ms**
- Entry animations: **200ms**
- Exit animations: **100-150ms** (faster feels responsive)
- Reordering (`animate:flip`): **200-300ms**
- Never exceed 300ms except for reordering

### Accessibility

- Dynamic messages with transitions: add `role="alert"` + `aria-live="polite"`
- Dismiss buttons: `aria-label`, minimum 44×44px
- Respect `prefers-reduced-motion`

### Use centralized animation constants

Define durations and easing in `src/lib/config/animations.ts`. Don't hardcode
timing values in individual components.

---

## Security

- **No `{@html}` without DOMPurify.** `{@html userInput}` is an XSS vector.
  Always sanitize: `{@html DOMPurify.sanitize(content)}`
- **No secrets in frontend code.** API keys stay in the backend.
  Only `VITE_` prefixed env vars are safe for frontend.
- **Auth check in every server action.** Always check `locals.user` before processing.
- **Test credentials from environment**, never hardcoded. Use `.env.test` (in `.gitignore`).

---

## Testing

Follow the **testing-discipline** skill for testing philosophy. Frontend-specific rules:

- **Utils/pure functions:** Vitest, no mocks needed
- **Components:** Vitest + `@testing-library/svelte` + `userEvent`
  - Test from user perspective: render, interact, assert on DOM
  - Use `getByRole`, `getByLabelText`, `getByText` — not `getByTestId`
  - No snapshot tests on large components
- **E2E:** Playwright for critical flows
- **Test file naming:** `feature.test.ts` for unit/component, `feature.spec.ts` for e2e
- **Every test** must have a `# CATCHES:` comment per the testing-discipline skill

---

## Checklist: Every Frontend Change

- [ ] All types explicit (no implicit `any`)
- [ ] Props typed with `$props<Props>()`
- [ ] Forms validated server-side with Superforms + Zod
- [ ] Form inputs bound to `$formData` (not separate state)
- [ ] Server actions use `locals.token`, not `apiClient`
- [ ] Error handling at appropriate level (route/component/form)
- [ ] Loading states on all async operations
- [ ] Semantic HTML with ARIA attributes
- [ ] Touch targets ≥ 44×44px
- [ ] Tested at 375px with no overflow
- [ ] `{@html}` sanitized with DOMPurify
- [ ] Auth checked in server actions
