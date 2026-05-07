---
paths:
  - frontend/src/lib/stores/**/*.ts
---

# Store Rules

Store files are plain TypeScript — they are not compiled by Svelte.
Runes (`$state`, `$derived`, `$effect`) do not work here.

## Use Svelte Store Primitives

```typescript
import { writable, derived, get } from "svelte/store";

// Writable store
export const authUser = writable<User | null>(null);

// Derived store
export const isAuthenticated = derived(authUser, ($user) => $user !== null);
```

## Decision Guide

| State scope                       | Use                                              |
| --------------------------------- | ------------------------------------------------ |
| Only used in one component        | `$state` in the `.svelte` file                   |
| Shared across pages or components | `writable` store in this directory               |
| Computed from other state         | `derived` store here, or `$derived` in `.svelte` |

## No Business Logic in Stores

Stores hold state. They do not fetch data, call APIs, or contain domain logic.
Data fetching belongs in `onMount` in the component or in a `+page.server.ts` load function.

## Typing

All stores must be typed. No implicit `any`.

```typescript
// YES
export const symptoms = writable<SymptomLog[]>([]);

// NO
export const symptoms = writable([]);
```

## Testing Stores

Test the logic, not the reactivity mechanism. Use `get()` to read current value.

```typescript
import { get } from "svelte/store";

// CATCHES: Filter includes archived items in the active view
test("activeItems excludes archived", () => {
  const store = createItemStore([
    { id: "1", archived: false },
    { id: "2", archived: true },
  ]);
  expect(get(store.activeItems)).toHaveLength(1);
});
```
