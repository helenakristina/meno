# Frontend V2 Code Standards (SvelteKit + TypeScript)

**Status:** Living document for V2 and beyond
**Last Updated:** March 11, 2026
**Framework:** SvelteKit 2.x + Svelte 5 runes

---

## Overview

This document establishes patterns and best practices for the Meno frontend to ensure:

- **Type Safety:** Full TypeScript coverage with no implicit `any`
- **Form Handling:** Consistent validation with Zod + Superforms
- **State Management:** Clear reactive patterns with Svelte stores
- **Testing:** Unit tests (Vitest), component tests (Testing Library), e2e (Playwright)
- **Error Handling:** Predictable, user-friendly error flow
- **Accessibility:** WCAG 2.1 Level AA compliance
- **Responsiveness:** Mobile-first (375px) with zero issues

**Refer to this document every time you add frontend code.** This is not a suggestion—it's the standard.

---

## Part 1: Type Safety

### 1.1 Global App Types (app.d.ts)

Define all SvelteKit global types upfront. This document is your contract with TypeScript.

```typescript
// frontend/src/app.d.ts

import type { User } from "@supabase/supabase-js";

declare global {
  namespace App {
    interface Error {
      message: string;
      code?: string;
      details?: Record<string, unknown>;
    }

    interface Locals {
      user?: {
        id: string;
        email: string;
      };
    }

    interface PageData {
      user?: User | null;
      [key: string]: unknown;
    }

    // PageState is used for client-only state that persists across navigation
    interface PageState {
      // Example: preserving form state while navigating
      formState?: Record<string, unknown>;
      scrollPosition?: number;
    }
  }
}

export {};
```

**Key Rules:**

- `Error` is what gets thrown to `+error.svelte` pages
- `Locals` is for server-side context (use in `+layout.server.ts`)
- `PageData` is the base type for all page data (extend with specific types per route)
- `PageState` is client-only state that survives navigation

---

### 1.2 Shared Type Definitions

Create a `lib/types/` folder for domain types. Don't scatter types across files.

```typescript
// frontend/src/lib/types/index.ts
// Central export point for all types

export type { User } from "./user";
export type { Chat, Message, Citation } from "./chat";
export type { SymptomLog, Symptom } from "./symptoms";
export type { Provider, Shortlist } from "./providers";

// Re-export API error type
export type { ApiError } from "../api/client";
```

**Example: Chat Types**

```typescript
// frontend/src/lib/types/chat.ts

export interface Citation {
  url: string;
  title: string;
  section: string;
  source_index: number;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp?: string;
}

export interface ChatApiResponse {
  message: string;
  citations: Citation[];
  conversation_id: string;
}

export interface ChatState {
  messages: Message[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
}
```

**Key Rules:**

- One domain = one file (chat.ts, symptoms.ts, etc.)
- Export from `index.ts` for clean imports
- Use `interface` for object types (more extensible than `type`)
- Include state types alongside domain types

---

### 1.3 Component Props with Type Safety

Always type component props explicitly. Use `$props` in Svelte 5.

```typescript
// ✅ GOOD: Explicit types, with defaults where sensible
interface ButtonProps {
  label: string;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  loading?: boolean;
  onclick?: () => void | Promise<void>;
}

let {
  label,
  variant = "primary",
  disabled = false,
  loading = false,
  onclick,
} = $props<ButtonProps>();

// ❌ BAD: Implicit types, no defaults
let label, variant, disabled, loading, onclick;
```

**Guidelines:**

- Use `$props()` with explicit type parameter
- Provide `?` for optional props
- Include defaults for boolean/enum props
- Document props with JSDoc when non-obvious

---

### 1.4 API Endpoint Types

Never use bare `fetch()` or untyped API calls. Define endpoint types once.

```typescript
// frontend/src/lib/types/api.ts

/**
 * Maps API endpoints to their request/response types.
 * Add an entry every time you add an API endpoint.
 */
export interface ApiEndpoints {
  // Chat endpoints
  "/api/chat": {
    request: { message: string; conversation_id?: string };
    response: {
      message: string;
      citations: Citation[];
      conversation_id: string;
    };
  };

  // Symptom endpoints
  "/api/symptoms/logs": {
    request: { symptoms: string[]; source: "cards" | "export" };
    response: { id: string; symptoms: string[]; logged_at: string };
  };
  "/api/symptoms/logs/get": {
    request: { start_date?: string; end_date?: string; limit?: number };
    response: { logs: SymptomLog[]; total: number };
  };

  // Provider endpoints
  "/api/providers/shortlist": {
    request: never;
    response: { provider_id: string }[];
  };
  "/api/providers/search": {
    request: { query: string; state?: string };
    response: Provider[];
  };

  // User endpoints
  "/api/users/profile": {
    request: never;
    response: {
      id: string;
      email: string;
      age?: number;
      journey_stage?: string;
    };
  };
}

// Type-safe API call wrapper
export type ApiMethod = keyof ApiEndpoints;
export type ApiRequest<T extends ApiMethod> = ApiEndpoints[T]["request"];
export type ApiResponse<T extends ApiMethod> = ApiEndpoints[T]["response"];
```

**Usage Examples:**

```typescript
// ✅ TYPED: Known endpoint, full type safety
const chatResponse = await apiClient.post("/api/chat", {
  message: "Hello",
  conversation_id: "123",
});
// TypeScript checks:
// - path '/api/chat' is valid
// - body must have message and optional conversation_id
// - chatResponse has message and citations fields

// ✅ ESCAPE HATCH: Unknown endpoint, explicit generic
const customResponse = await apiClient.post<MyCustomType>(
  "/api/custom/endpoint",
  { some: "data" },
);
// TypeScript allows any path and body, returns MyCustomType
// Use only for ad-hoc or external APIs

// ❌ TYPE ERROR: Can't use typed endpoint with wrong body
await apiClient.post("/api/chat", {
  // ERROR: missing 'message' field
  conversation_id: "123",
});
```

---

## Part 2: Form Validation

Use **Zod** + **Superforms** for type-safe, server-safe forms. Never validate only on client.

### 2.1 Define Schemas with Zod

```typescript
// frontend/src/lib/schemas/chat.ts

import { z } from "zod";

export const chatMessageSchema = z.object({
  message: z
    .string()
    .min(1, "Message cannot be empty")
    .max(2000, "Message must be under 2000 characters")
    .trim(),
  conversation_id: z.string().uuid().optional(),
});

export type ChatMessage = z.infer<typeof chatMessageSchema>;
```

**Key Rules:**

- One schema per form/operation
- Include validation messages (shown to user)
- Export both schema and inferred `type`
- Use `.trim()` on strings (removes accidental whitespace)

### 2.2 Server-Side Form Handler (+page.server.ts)

Always validate on server, even if client also validates.

```typescript
// frontend/src/routes/(app)/ask/+page.server.ts

import { fail, type Actions } from "@sveltejs/kit";
import { superValidate } from "sveltekit-superforms";
import { zod } from "sveltekit-superforms/adapters";
import { chatMessageSchema } from "$lib/schemas/chat";
import { apiClient } from "$lib/api/client";

export const actions: Actions = {
  async chat({ request, locals }) {
    // Validate request
    const form = await superValidate(request, zod(chatMessageSchema));

    if (!form.valid) {
      return fail(400, { form }); // Returns form with errors
    }

    // Check auth (from Locals set in +layout.server.ts)
    if (!locals.user) {
      return fail(401, { form, error: "Not authenticated" });
    }

    try {
      // Send to API
      const response = await apiClient.post("/api/chat", {
        message: form.data.message,
        conversation_id: form.data.conversation_id,
      });

      return {
        form,
        success: true,
        response,
      };
    } catch (error) {
      // Log server-side, return user-friendly message
      console.error("Chat API error:", error);
      return fail(500, {
        form,
        error: "Failed to get response. Please try again.",
      });
    }
  },
};
```

### 2.3 Client-Side Form Component

```typescript
// frontend/src/routes/(app)/ask/+page.svelte

<script lang="ts">
  import { superForm } from 'sveltekit-superforms/client';
  import { zod } from 'sveltekit-superforms/adapters';
  import { chatMessageSchema } from '$lib/schemas/chat';

  let { data } = $props();

  const form = superForm(data.form, {
    validators: zod(chatMessageSchema),
    delayMs: 200, // Debounce client-side validation
  });

  const { form: formData, errors, enhance, submitting } = form;
</script>

<form use:enhance method="POST" action="?/chat">
  <!-- ✅ Bind directly to $formData — this is what gets submitted -->
  <textarea
    name="message"
    bind:value={$formData.message}
    placeholder="Ask a question..."
    disabled={$submitting}
    aria-invalid={!!$errors.message}
    aria-describedby={$errors.message ? 'message-error' : undefined}
  />

  {#if $errors.message}
    <p id="message-error" class="text-sm text-red-600" role="alert">
      {$errors.message}
    </p>
  {/if}

  <button type="submit" disabled={$submitting}>
    {$submitting ? 'Sending...' : 'Send'}
  </button>
</form>
```

**Key Rules:**

- **Always bind directly to `$formData`** — this is what gets submitted to the server
- Always validate server-side with Superforms
- Client-side validation is UX enhancement, not security
- Display errors with `$errors` from form
- Link errors with `aria-describedby` for accessibility
- Disable submit button while `$submitting`
- Use `use:enhance` for progressive enhancement

### 2.3.1 Form Data Binding: Single Source of Truth

**Rule:** Form inputs must bind to `$formData` from Superforms, not a separate local state variable.

#### Why This Matters

When you create a separate local state (`let message = $state('')`) and bind to it instead of `$formData.message`:

```typescript
// ❌ WRONG: Two separate things
let message = $state('');  // Local state
<textarea bind:value={message} />  // Bound to local state

// User types "hello" → message = "hello"
// But $formData.message remains empty
// Form submits $formData.message (empty!)
```

The form submits `$formData`, not your local state. They become out of sync silently.

```typescript
// ✅ CORRECT: One source of truth
<textarea bind:value={$formData.message} />

// User types "hello" → $formData.message = "hello"
// Form submits $formData.message ✅
```

#### Pattern: Direct Binding (Recommended)

Bind form inputs directly to `$formData`:

```svelte
<textarea bind:value={$formData.message} />
<input bind:value={$formData.email} />
<input type="checkbox" bind:checked={$formData.subscribe} />
```

**Pros:**
- Simple, one source of truth
- No sync bugs
- User input always matches submitted data

**Cons:**
- Can't easily clear field after submit (would need to manually reset `$formData`)
- No local UX state (character count, unsaved indicator)

#### Pattern: Synced Local State (For UX Features)

If you need local state for UX (clearing after submit, character counting, unsaved badge), sync it back to `$formData`:

```svelte
<script>
  const form = superForm(...);
  const { form: formData } = form;

  let localMessage = $state('');
  let isSubmitting = $state(false);

  // Keep $formData in sync with local state
  $effect(() => {
    $formData.message = localMessage;
  });

  async function handleSuccess() {
    localMessage = '';  // Clear after submit
  }
</script>

<!-- Bound to local state (synced to $formData via $effect) -->
<textarea bind:value={localMessage} />
```

**Pros:**
- Can implement UX features (clearing, character count, unsaved indicators)
- Still maintains sync between input and submitted data

**Cons:**
- More complex, requires explicit sync logic
- Easier to introduce sync bugs if not careful

#### Anti-Pattern: Separate Unsynced States

```typescript
// ❌ DON'T: This loses user input
let message = $state('');  // Local state
const { form: formData } = form;

<textarea bind:value={message} />

// Submits formData.message (likely empty), not the typed message
// Data loss without any indication to user
```

### 2.2.1 Server-Side API Calls: Using the Auth Token from Locals

**⚠️ CRITICAL:** The browser `apiClient` in Part 11 cannot be used in `+page.server.ts`. It depends on `supabase.auth.getSession()`, which only exists in the browser. Server-side requires a different approach.

#### Architecture: Where Auth Tokens Come From

```
Browser: apiClient.getToken()
  ↓
  Calls: supabase.auth.getSession()
  ↓
  Returns: Bearer token for FastAPI

Server: +page.server.ts
  ↗ CAN'T use apiClient (no browser)
  ↓
  Use: locals.user from +layout.server.ts
  ↓
  Token is set by: +layout.server.ts → verifyAuth()
  ↓
  Comes from: Supabase session cookie (set by Supabase on login)
```

#### Pattern: Server-Side API Calls in Actions

```typescript
// frontend/src/routes/(app)/+layout.server.ts
// Sets up locals with auth token

import { verifyAuth } from "$lib/supabase/server";

export const load = async ({ locals, cookies }) => {
  const session = await verifyAuth(cookies);
  locals.user = session?.user || null;
  locals.token = session?.access_token || null;
  return { user: locals.user };
};
```

```typescript
// frontend/src/routes/(app)/appointment-prep/+page.server.ts
// Uses the token from locals

import { fail, type Actions } from "@sveltejs/kit";
import { superValidate } from "sveltekit-superforms";
import { zod } from "sveltekit-superforms/adapters";
import { appointmentContextSchema } from "$lib/schemas/appointment";

export const actions: Actions = {
  async context({ request, locals }) {
    // Validate input
    const form = await superValidate(request, zod(appointmentContextSchema));

    if (!form.valid) {
      return fail(400, { form });
    }

    // Check auth (from locals, set in +layout.server.ts)
    if (!locals.user || !locals.token) {
      return fail(401, { form, error: "Not authenticated" });
    }

    // Call FastAPI backend using fetch + token from locals
    try {
      const response = await fetch(
        "http://localhost:8000/api/appointment-prep/context",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${locals.token}`, // ← Token from locals
            "Content-Type": "application/json",
          },
          body: JSON.stringify(form.data),
        },
      );

      if (!response.ok) {
        return fail(response.status, {
          form,
          error: `API error: ${response.statusText}`,
        });
      }

      const data = await response.json();

      return {
        form,
        success: true,
        appointmentId: data.appointment_id,
      };
    } catch (error) {
      return fail(500, {
        form,
        error: "Failed to create appointment context",
      });
    }
  },
};
```

#### Key Differences: Browser Client vs. Server Fetch

```typescript
// ❌ WRONG: Can't use browser apiClient in +page.server.ts
export const actions = {
  async context({ request }) {
    const form = await superValidate(request, zod(schema));

    // ERROR: apiClient needs supabase.auth.getSession()
    // which doesn't exist server-side
    const result = await apiClient.post(
      "/api/appointment-prep/context",
      form.data,
    );
  },
};

// ✅ RIGHT: Use fetch + token from locals
export const actions = {
  async context({ request, locals }) {
    const form = await superValidate(request, zod(schema));

    // Get token from locals (set in +layout.server.ts)
    if (!locals.token) {
      return fail(401, { form, error: "Not authenticated" });
    }

    // Use native fetch with Bearer token
    const response = await fetch("http://localhost:8000/api/...", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${locals.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(form.data),
    });

    return response.json();
  },
};
```

#### Server-Side API Helper (Optional)

If you have many server actions calling the API, create a helper to reduce duplication:

```typescript
// frontend/src/lib/api/server.ts

export async function serverFetch<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: unknown;
    token: string; // Passed from locals.token
  },
): Promise<T> {
  const baseUrl = "http://localhost:8000";
  const url = new URL(path, baseUrl);

  const response = await fetch(url, {
    method: options.method || "GET",
    headers: {
      Authorization: `Bearer ${options.token}`,
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
```

Then use it in actions:

```typescript
import { serverFetch } from "$lib/api/server";

export const actions = {
  async context({ request, locals }) {
    const form = await superValidate(request, zod(schema));

    if (!form.valid || !locals.token) {
      return fail(400, { form });
    }

    try {
      const data = await serverFetch("/api/appointment-prep/context", {
        method: "POST",
        body: form.data,
        token: locals.token,
      });

      return { form, success: true, appointmentId: data.appointment_id };
    } catch (error) {
      return fail(500, { form, error: error.message });
    }
  },
};
```

#### Environment Configuration

The FastAPI base URL should be an environment variable (not hardcoded `localhost:8000`):

```bash
# frontend/.env.local
VITE_API_BASE_URL=http://localhost:8000  # For browser client
SECRET_API_BASE_URL=http://backend:8000  # For server-side (internal network)
```

```typescript
// frontend/src/lib/api/server.ts

const SERVER_API_BASE_URL =
  import.meta.env.SECRET_API_BASE_URL || "http://localhost:8000";
```

This allows different URLs for browser (public) vs. server (internal).

---

## Part 3: State Management

### The Stores vs. Runes Boundary (Important!)

**TL;DR:** Use `$state` and `$derived` in `.svelte` files. Use `writable`/`derived` from `svelte/store` in plain `.ts` files. Both will eventually merge, but today they have different scopes.

**Why both exist:**

Svelte 5 runes (`$state`, `$derived`, `$effect`) only work inside:

- `.svelte` component files
- `.svelte.ts` files (rune-aware modules — coming soon)

Svelte 5 runes do **NOT** work in plain `.ts` files (module context). That's why you need `svelte/store` for:

- Shared authentication state (`authStore.ts`)
- Global app state (`themeStore.ts`)
- Services that manage state (`sessionStore.ts`)

**The Technical Reason:**

Runes are compiled by Svelte's compiler. Plain `.ts` files aren't compiled by Svelte, so the compiler can't recognize `$state`. Stores use runtime reactivity instead, which works anywhere.

**Migration Path:**

Svelte 5's "universal reactivity" (runes everywhere) is coming. When it lands:

- We'll convert `.ts` stores to `.svelte.ts` files
- All state will use `$state` and `$derived`
- `svelte/store` becomes optional

**For now, the rule is simple:**

| File Type                | Use This              | Example                                  |
| ------------------------ | --------------------- | ---------------------------------------- |
| `.svelte`                | `$state`, `$derived`  | `let count = $state(0)`                  |
| `.svelte.ts` (future)    | `$state`, `$derived`  | When available                           |
| `.ts` (plain JS modules) | `writable`, `derived` | `export const authStore = writable(...)` |

**Common mistake:**

```typescript
// ❌ WRONG: $state doesn't work in .ts files
// authStore.ts
export let user = $state(null); // ERROR: $ is not defined

// ✅ RIGHT: Use writable in .ts files
// authStore.ts
import { writable } from "svelte/store";
export const authStore = writable(null);
```

**Both approaches are correct right now.** Don't mix them in the same file (confusing), but use the right tool for the right context.

---

### 3.1 Svelte Stores for Shared State

Use Svelte's built-in stores (writable, readable, derived). Don't over-engineer.

```typescript
// frontend/src/lib/stores/auth.ts

import { writable, type Writable } from "svelte/store";
import type { User } from "@supabase/supabase-js";

export interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Auth state store. Manages user session + loading/error states.
 * Subscribe to this in root layout to show loading spinner during auth check.
 */
export const authState: Writable<AuthState> = writable({
  user: null,
  isLoading: true, // Start with loading=true
  error: null,
});

export async function initializeAuth() {
  try {
    const { data } = await supabase.auth.getSession();
    authState.set({
      user: data.session?.user ?? null,
      isLoading: false,
      error: null,
    });
  } catch (error) {
    authState.set({
      user: null,
      isLoading: false,
      error: "Failed to load session",
    });
  }
}
```

**Why `writable` here instead of `$state`?**

This file is `.ts` (plain TypeScript), not `.svelte`. Runes like `$state` only work in `.svelte` files. Stores work in both `.ts` and `.svelte` files, so they're the right choice for shared state in modules.

In components, you can subscribe to this store:

```svelte
<!-- Component can use runes for local state, subscribe to stores for shared state -->
<script lang="ts">
  import { authState } from '$lib/stores/auth';

  let localCount = $state(0);  // ✅ Rune (local component state)

  // Subscribe to store (shared state)
  $: auth = $authState;  // ✅ Store subscription (shared across app)
</script>

<p>User: {auth.user?.email}</p>
<p>Loading: {auth.isLoading}</p>
<p>Count: {localCount}</p>
```

---

### 3.2 Derived Stores for Computed State

```typescript
// frontend/src/lib/stores/app.ts

import { writable, derived } from "svelte/store";

export const symptoms = writable<SymptomLog[]>([]);
export const medications = writable<Medication[]>([]);

// Automatically updates when symptoms or medications change
export const userHasData = derived(
  [symptoms, medications],
  ([$symptoms, $medications]) => {
    return $symptoms.length > 0 || $medications.length > 0;
  },
);

// Usage:
// {#if $userHasData}
//   Show dashboard
// {:else}
//   Show empty state
// {/if}
```

### 3.3 Decision Tree: Stores vs. Local State vs. Runes

**Step 1: Where is your code?**

```
Is it in a `.svelte` file?
├─ YES → Is state shared across components?
│  ├─ YES → Subscribe to a store (see 3.1)
│  └─ NO → Use $state (see example below)
│
└─ NO (plain `.ts` file) → Use svelte/store (writable/derived)
   └─ See 3.1 for examples
```

**Step 2: Quick Reference**

| Scenario                        | Use This           | File Type | Example                                  |
| ------------------------------- | ------------------ | --------- | ---------------------------------------- |
| Component-local counter         | `$state`           | `.svelte` | `let count = $state(0)`                  |
| Computed value in component     | `$derived`         | `.svelte` | `let doubled = $derived(count * 2)`      |
| Shared auth across app          | `writable` store   | `.ts`     | `export const authStore = writable(...)` |
| Subscribe to store in component | Store subscription | `.svelte` | `$: user = $authStore`                   |
| Side effect in component        | `$effect`          | `.svelte` | `$effect(() => { ... })`                 |

**Step 3: Component-Local State Example**

For state that doesn't need to be shared, use `$state` in the component:

```typescript
// ✅ GOOD: Local to component
let messages = $state<Message[]>([]);
let isLoading = $state(false);
let error = $state<string | null>(null);

// ❌ BAD: Same state in a store when it's only used here
// export const messages = writable<Message[]>([]);
```

**Step 4: Don't Mix!**

```typescript
// ❌ BAD: Don't mix runes and stores in the same file
// authStore.ts
let user = $state(null); // ERROR: Can't use runes in .ts
export const authStore = writable(user); // ERROR: $state doesn't exist

// ✅ GOOD: Use the right tool for context
// authStore.ts (plain .ts file)
export const authStore = writable(null);

// MyComponent.svelte (component file)
let localCount = $state(0); // ✅ Rune in .svelte
const user = $authStore; // ✅ Store subscription in .svelte
```

**Decision Shortcut:**

- **Shared across pages?** → Store (`.ts` file with `writable`)
- **Persists across navigation?** → Store
- **Only used in this component?** → `$state` (`.svelte` file)
- **Computed from another store?** → Derived store (in `.ts`) or `$derived` (in `.svelte`)
- **When in doubt:** If your code is in a `.ts` file, use `svelte/store`. If it's in a `.svelte` file and state isn't shared, use runes.

---

## Part 4: Error Handling

Svelte and SvelteKit provide different error handling mechanisms depending on context:

- **Route-level** (server and page components): Use SvelteKit's `+error.svelte`
- **Component-level** (within components): Use try/catch + reactive state
- **Complex async flows**: Use the `<AsyncLoader>` wrapper component for cleaner code

### 4.1 Predictable Error Types

```typescript
// frontend/src/lib/types/api.ts

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  timestamp: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.timestamp = new Date().toISOString();
  }
}

// Usage: throw new ApiError(404, 'NOT_FOUND', 'User not found');
```

**Why ApiError is a class:** `ApiError` extends `Error` and is constructed with `new ApiError(...)`. This makes `error instanceof ApiError` checks work correctly at runtime. If it were just an interface with object literals, the instanceof checks would always fail.

Example client usage:

```typescript
// frontend/src/lib/api/client.ts

function parseApiError(status: number, body: unknown): ApiError {
  let detail = `Request failed with status ${status}`;
  let code = `HTTP_${status}`;

  if (body && typeof body === "object") {
    const err = body as Record<string, unknown>;
    if (typeof err.detail === "string") {
      detail = err.detail;
    }
    if (typeof err.code === "string") {
      code = err.code;
    }
  }

  return new ApiError(status, code, detail);
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  try {
    const response = await fetch(path, {
      method,
      headers: { Authorization: `Bearer ${token}` },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      let bodyData: unknown;
      try {
        bodyData = await response.json();
      } catch {
        // Not JSON
      }
      throw parseApiError(response.status, bodyData);
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error; // Already an API error
    }

    // Network error or JSON parse error
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Network error. Check your connection.",
    );
  }
}
```

### 4.2 Error Handling in Components

```typescript
// In a component:

import type { ApiError } from "$lib/types";

let error = $state<ApiError | null>(null);

async function sendMessage() {
  error = null; // Clear previous error

  try {
    const response = await apiClient.post("/api/chat", { message });
    // Success
  } catch (err) {
    // ✅ NOW WORKS CORRECTLY: instanceof checks pass because ApiError is a real class
    if (err instanceof ApiError) {
      // Handle specific error codes
      if (err.status === 401) {
        error = err;
        // Redirect to login
      } else if (err.status === 429) {
        error = err;
      } else {
        error = err;
      }
    } else {
      // Unexpected error type
      console.error("Unexpected error:", err);
      error = new ApiError(
        500,
        "UNKNOWN_ERROR",
        "An unexpected error occurred",
      );
    }
  }
}
```

**Why instanceof works now:** `ApiError` is a proper class (extends `Error`, constructed with `new`), so `error instanceof ApiError` checks work at runtime. Object literals with interfaces don't support instanceof checks.

### 4.3 Error Handling in Components

Svelte doesn't have built-in error boundaries like React. Instead, use SvelteKit's route-level error handling and component-level try/catch.

#### Route-Level Errors (SvelteKit +error.svelte)

SvelteKit catches errors in `+page.server.ts` and `+layout.server.ts` and renders `+error.svelte`:

```typescript
// frontend/src/routes/(app)/+page.server.ts

export const load = async () => {
  const data = await fetchData(); // If this throws, caught by SvelteKit
  return data;
};
```

```svelte
<!-- frontend/src/routes/+error.svelte -->

<script>
  import { page } from '$app/stores';
</script>

<div role="alert" class="rounded-lg bg-red-50 p-4">
  <h1 class="font-bold text-red-900">Something went wrong</h1>
  <p class="text-sm text-red-700">{$page.error?.message}</p>
</div>
```

#### Component-Level Errors (Try/Catch + State)

For errors within components, use try/catch and render based on state:

```svelte
<!-- ✅ GOOD: Component catches and handles errors -->

<script lang="ts">
  let data = $state(null);
  let error = $state<Error | null>(null);
  let isLoading = $state(false);

  async function fetchData() {
    isLoading = true;
    error = null;
    try {
      data = await apiClient.get('/api/data');
    } catch (e) {
      error = e instanceof Error ? e : new Error(String(e));
    } finally {
      isLoading = false;
    }
  }

  // Fetch on mount
  $effect(() => {
    fetchData();
  });
</script>

{#if isLoading}
  <div class="flex justify-center p-4">
    <Spinner />
  </div>
{:else if error}
  <div role="alert" class="rounded-lg bg-red-50 p-4">
    <p class="text-sm text-red-700">{error.message}</p>
    <button onclick={fetchData} class="mt-2 text-red-700 underline">Retry</button>
  </div>
{:else}
  <div>{JSON.stringify(data)}</div>
{/if}
```

#### AsyncLoader: Wrapper Component (Advanced Pattern)

For complex flows that need to handle errors from nested async operations, use a wrapper component:

```svelte
<!-- frontend/src/lib/components/AsyncLoader.svelte -->

<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    /**
     * Async function to execute. If it throws, error is caught and rendered.
     */
    loader: () => Promise<void>;
    /**
     * Main content to render on success.
     */
    children: Snippet;
    /**
     * Optional fallback to render on error. Receives the Error object.
     */
    fallback?: Snippet<[error: Error]>;
    /**
     * Optional loading state (for long-running operations).
     */
    loading?: Snippet;
  }

  let { loader, children, fallback, loading } = $props<Props>();

  let error = $state<Error | null>(null);
  let isLoading = $state(false);

  // Run loader on mount and when loader changes
  $effect(() => {
    isLoading = true;
    error = null;

    loader()
      .catch((e) => {
        error = e instanceof Error ? e : new Error(String(e));
      })
      .finally(() => {
        isLoading = false;
      });
  });
</script>

{#if isLoading && loading}
  {@render loading()}
{:else if error && fallback}
  {@render fallback(error)}
{:else if error}
  <!-- Default error UI -->
  <div role="alert" class="rounded-lg bg-red-50 p-4">
    <h2 class="font-semibold text-red-900">Error loading content</h2>
    <p class="text-sm text-red-700">{error.message}</p>
  </div>
{:else}
  {@render children()}
{/if}
```

**Usage:**

```svelte
<AsyncLoader
  loader={async () => {
    const data = await fetchUserData();
    user = data;
  }}
  loading={<Spinner />}
  fallback={(error) => (
    <div class="text-red-600">
      <p>{error.message}</p>
      <button onclick={() => location.reload()}>Reload</button>
    </div>
  )}
>
  <UserCard {user} />
</AsyncLoader>
```

#### Key Patterns

**❌ Don't:**

```svelte
<!-- Don't assume fetch won't throw -->
<script>
  let data = fetch('/api/data');
</script>
```

**✅ Do:**

```svelte
<!-- Wrap in try/catch -->
<script>
  let data = null;
  let error = null;

  $effect(() => {
    fetch('/api/data')
      .then(r => r.json())
      .then(d => { data = d; })
      .catch(e => { error = e; });
  });
</script>

{#if error}
  <ErrorMessage {error} />
{:else}
  <Content {data} />
{/if}
```

**Summary:**

- **Route-level:** Use SvelteKit's `+error.svelte`
- **Component-level:** Use try/catch + state
- **Complex flows:** Use `<AsyncLoader>` wrapper for cleaner code

### 4.4 Form Error Handling with Superforms

Form validation errors (from the server) are handled differently than async errors. Superforms provides `$errors` object with field-level error messages.

**Complete example with proper binding and error display:**

```svelte
<!-- frontend/src/routes/(app)/ask/+page.svelte -->

<script lang="ts">
  import { superForm } from 'sveltekit-superforms/client';
  import { zod } from 'sveltekit-superforms/adapters';
  import { chatMessageSchema } from '$lib/schemas/chat';

  let { data } = $props();

  const form = superForm(data.form, {
    validators: zod(chatMessageSchema),
    delayMs: 200, // Debounce client-side validation
  });

  const { form: formData, errors, enhance, submitting } = form;
</script>

<form use:enhance method="POST" action="?/chat" class="space-y-4">
  <!-- Input field with error aria labels -->
  <div>
    <label for="message" class="block text-sm font-medium mb-2">
      Message
    </label>
    <textarea
      id="message"
      name="message"
      bind:value={$formData.message}
      placeholder="Ask a question..."
      disabled={$submitting}
      aria-invalid={!!$errors.message}
      aria-describedby={$errors.message ? 'message-error' : undefined}
      class="w-full p-2 border rounded"
      class:border-red-500={!!$errors.message}
    />

    <!-- Error message linked with aria-describedby -->
    {#if $errors.message}
      <p
        id="message-error"
        class="mt-1 text-sm text-red-600"
        role="alert"
      >
        {$errors.message}
      </p>
    {/if}
  </div>

  <button
    type="submit"
    disabled={$submitting}
    class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
  >
    {$submitting ? 'Sending...' : 'Send'}
  </button>

  <!-- Optional: Show server-side error if form submission failed -->
  {#if $page.form?.error}
    <div role="alert" class="rounded-lg bg-red-50 p-4">
      <p class="text-sm text-red-700">{$page.form.error}</p>
    </div>
  {/if}
</form>
```

**Key accessibility patterns:**

- **`aria-invalid={!!$errors.message}`** — Screen readers announce field has validation error
- **`aria-describedby="message-error"`** — Links error message to input (screen reader announces both)
- **`<label for="id">`** — Labels all inputs with `for` attribute
- **`role="alert"`** — Error messages announced as alerts
- **Visual feedback** — Red border on invalid fields

**Server-side validation (from Part 2.2):**

```typescript
// frontend/src/routes/(app)/ask/+page.server.ts

import { fail } from "@sveltejs/kit";
import { superValidate } from "sveltekit-superforms";
import { zod } from "sveltekit-superforms/adapters";
import { chatMessageSchema } from "$lib/schemas/chat";

export const actions = {
  async chat({ request, locals }) {
    // Validates and returns errors if invalid
    const form = await superValidate(request, zod(chatMessageSchema));

    if (!form.valid) {
      // Returns form with $errors populated
      // Component displays errors from $errors.message
      return fail(400, { form });
    }

    // Form is valid, process it
    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${locals.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form.data),
      });

      if (!response.ok) {
        // Server-side error (network, API, etc)
        return fail(response.status, {
          form,
          error: "Failed to send message. Please try again.",
        });
      }

      const data = await response.json();
      return { form, success: true, response: data };
    } catch (error) {
      return fail(500, {
        form,
        error: "Connection error. Please try again.",
      });
    }
  },
};
```

**How validation flows:**

```
User types → $formData.message = "hello"
            ↓
User clicks Submit
            ↓
Form POSTs to server action
            ↓
Server validates with Zod
            ↓
If invalid: return fail(400, { form }) with $errors populated
           ├─ Component receives form with errors
           └─ Displays $errors.message in UI
            ↓
If valid: Process and return success
```

---

## Part 5: Loading States

### 5.1 Standardized Loading Pattern

Every data-fetching operation should follow this pattern:

```typescript
let data = $state<MyData | null>(null);
let isLoading = $state(false);
let error = $state<string | null>(null);

async function fetchData() {
  isLoading = true;
  error = null;

  try {
    data = await apiClient.get("/api/some-endpoint");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load data";
    data = null;
  } finally {
    isLoading = false;
  }
}
```

### 5.2 Loading UI Components

```typescript
// frontend/src/lib/components/LoadingSpinner.svelte
<script lang="ts">
  interface Props {
    size?: 'sm' | 'md' | 'lg';
  }

  let { size = 'md' } = $props<Props>();

  const sizeClass = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };
</script>

<div role="status" aria-live="polite" aria-label="Loading">
  <div class={`animate-spin rounded-full border-2 border-slate-300 border-t-slate-600 ${sizeClass[size]}`} />
</div>
```

```typescript
// frontend/src/lib/components/SkeletonLoader.svelte
<script lang="ts">
  interface Props {
    lines?: number;
    variant?: 'title' | 'text' | 'card';
  }

  let { lines = 3, variant = 'text' } = $props<Props>();
</script>

<div class="space-y-2">
  {#each { length: lines } as _}
    <div
      class={`animate-pulse rounded ${
        variant === 'title' ? 'h-6 bg-slate-200' : 'h-4 bg-slate-100'
      }`}
    />
  {/each}
</div>
```

### 5.3 Use in Components

```typescript
{#if isLoading}
  <SkeletonLoader lines={5} />
{:else if error}
  <div class="rounded-lg bg-red-50 p-4 text-sm text-red-700">
    {error}
  </div>
{:else if data}
  <!-- Render data -->
{:else}
  <p class="text-slate-500">No data to display</p>
{/if}
```

---

## Part 6: Component Organization

### 6.1 Folder Structure

```
frontend/src
├── lib/
│   ├── components/
│   │   ├── ui/                ← shadcn-svelte components
│   │   │   ├── button/
│   │   │   ├── input/
│   │   │   └── index.ts
│   │   ├── forms/             ← Form components
│   │   │   ├── ChatForm.svelte
│   │   │   ├── SearchForm.svelte
│   │   │   └── index.ts
│   │   ├── layouts/           ← Layout components
│   │   │   ├── AppLayout.svelte
│   │   │   └── index.ts
│   │   └── shared/            ← Reusable components
│   │       ├── LoadingSpinner.svelte
│   │       ├── ErrorBoundary.svelte
│   │       └── index.ts
│   ├── api/
│   │   ├── client.ts          ← API client
│   │   └── index.ts
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── app.ts
│   │   └── index.ts
│   ├── types/
│   │   ├── index.ts
│   │   ├── api.ts
│   │   ├── chat.ts
│   │   └── index.ts
│   ├── schemas/
│   │   ├── chat.ts
│   │   ├── user.ts
│   │   └── index.ts
│   ├── utils/
│   │   ├── markdown.ts
│   │   └── index.ts
│   └── __tests__/             ← Unit tests
│       ├── utils.test.ts
│       └── markdown.test.ts
├── routes/
│   ├── (app)/
│   │   ├── ask/
│   │   │   ├── +page.svelte
│   │   │   ├── +page.server.ts
│   │   │   └── __tests__/     ← Component tests
│   │   │       └── +page.test.ts
│   │   └── ...
│   ├── (auth)/
│   │   └── ...
│   └── +layout.svelte
└── app.d.ts
```

### 6.2 Component Template (Svelte 5)

```typescript
// frontend/src/lib/components/MyComponent.svelte

<script lang="ts">
  /**
   * Brief description of what this component does.
   *
   * @example
   * <MyComponent title="Example" onAction={() => {}} />
   */

  import { derived } from 'svelte/store';
  import { Button } from '$lib/components/ui';

  interface Props {
    title: string;
    isActive?: boolean;
    onAction?: (value: string) => void;
  }

  let { title, isActive = false, onAction } = $props<Props>();

  let internalState = $state('');

  // Computed value
  let derivedValue = $derived(internalState.length > 0);

  function handleClick() {
    onAction?.(internalState);
  }
</script>

<div class="space-y-4">
  <h2 class="text-lg font-semibold">{title}</h2>
  <!-- Content -->
  <Button onclick={handleClick} disabled={!derivedValue}>
    Click me
  </Button>
</div>

<style>
  /* Component styles only (no global styles) */
</style>
```

---

## Part 7: Testing Strategy

### 7.1 Unit Tests (Vitest)

Test pure functions and utilities.

```typescript
// frontend/src/lib/__tests__/markdown.test.ts

import { describe, it, expect } from "vitest";
import { renderMarkdown, sanitizeMarkdownHtml } from "$lib/utils/markdown";

describe("renderMarkdown", () => {
  it("renders bold text correctly", () => {
    const result = renderMarkdown("This is **bold** text");
    expect(result).toContain("<strong>bold</strong>");
  });

  it("renders headers", () => {
    const result = renderMarkdown("## Heading");
    expect(result).toContain("<h2>Heading</h2>");
  });

  it("escapes XSS attempts", () => {
    const result = renderMarkdown('<script>alert("xss")</script>');
    expect(result).not.toContain("<script>");
  });

  it("handles empty string", () => {
    expect(renderMarkdown("")).toBe("");
  });
});
```

### 7.2 Component Tests (Vitest + Testing Library)

```typescript
// frontend/src/routes/(app)/ask/__tests__/+page.test.ts

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import AskMenoPage from "../+page.svelte";

describe("Ask Meno Page", () => {
  beforeEach(() => {
    // Reset mocks, auth state, etc.
  });

  it("renders empty state with starter prompts", () => {
    render(AskMenoPage, {
      props: { data: { form: { data: {} } } },
    });

    expect(screen.getByText(/What causes brain fog/)).toBeInTheDocument();
  });

  it("sends message on Enter key", async () => {
    const user = userEvent.setup();
    render(AskMenoPage, {
      props: { data: { form: { data: {} } } },
    });

    const textarea = screen.getByPlaceholderText(/Ask a question/);
    await user.type(textarea, "Test message");
    await user.keyboard("{Enter}");

    // Verify message was sent (check store, API call, etc.)
  });

  it("shows error message on API failure", async () => {
    // Mock API to fail
    vi.mock("$lib/api/client", () => ({
      apiClient: {
        post: vi.fn().mockRejectedValue(new Error("API error")),
      },
    }));

    const user = userEvent.setup();
    render(AskMenoPage, {
      props: { data: { form: { data: {} } } },
    });

    const textarea = screen.getByPlaceholderText(/Ask a question/);
    await user.type(textarea, "Test");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Something went wrong/,
      );
    });
  });

  it("renders citations as links", () => {
    render(AskMenoPage, {
      props: {
        data: {
          form: {
            data: {
              messages: [
                {
                  role: "assistant",
                  content: "Answer [Source 1]",
                  citations: [{ url: "https://example.com", title: "Example" }],
                },
              ],
            },
          },
        },
      },
    });

    const link = screen.getByRole("link", { name: /\[1\]/ });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
  });
});
```

### 7.2 Test Environment Setup

**Authentication for E2E tests:**

E2E tests need test credentials to log in. Create a `.env.test` file in the frontend directory:

```bash
# frontend/.env.test

# Test user credentials (username/password auth - current system)
TEST_USERNAME=testuser@example.com
TEST_PASSWORD=test_password_123

# These credentials should be for a dedicated test account in development
# Never use real user credentials in tests
```

**Creating a test account:**

1. Sign up manually in development with test credentials
2. Use those credentials in `.env.test`
3. `.env.test` is already in `.gitignore` — never commit it

**Future: Magic Link Migration**

When we migrate to magic links (see `docs/planning/V2_V3_ROADMAP.md`), this will change to use authenticated sessions instead of form filling. The `beforeEach` hook will be updated at that time.

---

### 7.3 E2E Tests (Current: Username/Password Auth)

_Note: Uses username/password login. Will change when migrating to magic links._

```typescript
// frontend/tests/e2e/ask-meno.spec.ts

import { test, expect } from "@playwright/test";

/**
 * Current authentication: username/password
 *
 * This logs in with credentials stored in .env.test
 * Future: Will migrate to magic links (see docs/planning/V2_V3_ROADMAP.md)
 */

test.describe("Ask Meno E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto("/login");

    // Fill in credentials from environment
    const username = process.env.TEST_USERNAME || "testuser@example.com";
    const password = process.env.TEST_PASSWORD || "test_password_123";

    await page.fill('input[type="email"]', username);
    await page.fill('input[type="password"]', password);

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard (auth successful)
    await page.waitForURL("/dashboard");
  });

  test("user can ask a question and see formatted response", async ({
    page,
  }) => {
    await page.goto("/ask");

    const textarea = page.locator("textarea");
    await textarea.fill("What causes hot flashes?");
    await page.click('button:has-text("Send")');

    // Wait for response
    await page.waitForSelector(
      '[aria-label="Chat messages"] >> text=hot flashes',
    );

    // Verify markdown is rendered (no ** visible)
    const messageText = await page
      .locator('[aria-label="Chat messages"]')
      .textContent();
    expect(messageText).not.toContain("**");

    // Verify citations are links
    const citations = await page.locator('a[target="_blank"]').count();
    expect(citations).toBeGreaterThan(0);
  });

  test("message input is cleared after sending", async ({ page }) => {
    await page.goto("/ask");

    const textarea = page.locator("textarea");
    await textarea.fill("Test message");
    await page.click('button:has-text("Send")');

    await page.waitForTimeout(500); // Wait for state update

    expect(await textarea.inputValue()).toBe("");
  });

  test("error message is shown on API failure", async ({ page }) => {
    // Mock API to fail
    await page.route("/api/chat", (route) => {
      route.abort("failed");
    });

    await page.goto("/ask");

    const textarea = page.locator("textarea");
    await textarea.fill("Test");
    await page.click('button:has-text("Send")');

    await expect(page.locator('[role="alert"]')).toContainText(
      /Something went wrong/,
    );
  });
});
```

### 7.4 Test File Naming

```
✅ GOOD:
- test_chat.test.ts (function name matches file)
- ask-meno.spec.ts (e2e tests)
- renderMarkdown.test.ts (unit tests for specific function)

❌ BAD:
- tests.ts (too generic)
- test.ts (no descriptor)
- ask_meno_chat_page_test.ts (too verbose)
```

---

## Part 8: Accessibility (WCAG 2.1 AA)

### 8.1 Semantic HTML

```svelte
<!-- ✅ GOOD -->
<nav>
  <a href="/" aria-current={page === 'home' ? 'page' : undefined}>Home</a>
</nav>

<main>
  <h1>Page Title</h1>
  <section aria-labelledby="section-title">
    <h2 id="section-title">Section Title</h2>
  </section>
</main>

<footer>Footer content</footer>

<!-- ❌ BAD -->
<div class="nav">
  <div class="link">Home</div>
</div>

<div class="main">
  <div class="title">Page Title</div>
</div>
```

### 8.2 Focus and Keyboard Navigation

```svelte
<!-- ✅ GOOD: Tab order, visible focus -->
<button onclick={handleClick} class="focus:outline-2 focus:outline-offset-2">
  Click me
</button>

<!-- Focus visible is a must (never outline: none) -->
<style>
  button:focus-visible {
    outline: 2px solid #0d9488;
    outline-offset: 2px;
  }
</style>

<!-- ❌ BAD: Hidden focus indicator -->
<button style="outline: none">Click me</button>
```

### 8.3 ARIA Labels

```svelte
<!-- Icon button needs aria-label -->
<button aria-label="Close dialog" onclick={close}>
  <svg><!-- Close icon --></svg>
</button>

<!-- Form inputs need labels -->
<label for="email">Email</label>
<input id="email" type="email" />

<!-- Expandable content needs aria-expanded -->
<button
  aria-expanded={isOpen}
  aria-controls="menu"
  onclick={() => isOpen = !isOpen}
>
  Menu
</button>
<div id="menu" hidden={!isOpen}>
  <!-- Menu items -->
</div>

<!-- Loading state -->
<div aria-live="polite" aria-busy={isLoading}>
  {#if isLoading}
    Loading...
  {/if}
</div>
```

### 8.4 Color Contrast

Text must have 4.5:1 ratio (normal) or 3:1 (large, 18px+).

```css
/* ✅ GOOD: 4.5:1 contrast */
.text {
  color: #1f2937; /* Dark gray on white */
  background: white;
}

/* ❌ BAD: Insufficient contrast */
.text {
  color: #999999; /* Gray on white, ~3:1 */
  background: white;
}
```

### 8.5 Touch Targets (44×44px minimum)

```svelte
<!-- ✅ GOOD: All interactive elements are 44×44px or larger -->
<button class="h-11 w-11 flex items-center justify-center">
  <svg><!-- Icon --></svg>
</button>

<input type="text" class="h-11 px-3" />

<!-- ❌ BAD: Too small to tap -->
<button class="p-1">
  <svg class="h-4 w-4" />
</button>
```

---

## Part 9: Responsive Design (Mobile-First)

Always test at **375px, 667px (landscape), 768px, 1440px**.

### 9.1 Container Patterns

```svelte
<!-- ✅ GOOD: Mobile-first, full width, max-width, no overflow -->
<div class="w-full max-w-full overflow-hidden">
  <div class="px-4 sm:px-6 lg:px-8">
    <!-- Content -->
  </div>
</div>

<!-- ❌ BAD: Fixed width, potential horizontal scroll -->
<div class="w-[1200px]">
  <!-- Content -->
</div>
```

### 9.2 Responsive Layouts

```svelte
<!-- ✅ GOOD: Flex wrapping for mobile -->
<div class="flex flex-col gap-4 sm:flex-row">
  <div class="flex-1">Column 1</div>
  <div class="flex-1">Column 2</div>
</div>

<!-- ❌ BAD: Fixed grid that breaks on mobile -->
<div class="grid grid-cols-2 gap-4">
  <div>Column 1</div>
  <div>Column 2</div>
</div>
```

### 9.3 Typography Scaling

```css
/* ✅ GOOD: Base size on mobile, scales up */
.text {
  font-size: 0.875rem; /* 14px on mobile */
}

@media (min-width: 640px) {
  .text {
    font-size: 1rem; /* 16px on tablet */
  }
}

/* ❌ BAD: Too small on mobile */
.text {
  font-size: 0.75rem; /* 12px everywhere */
}
```

---

## Part 10: Svelte 5 Runes (Reactive Variables)

Use Svelte 5's runes for all reactive state.

```typescript
// ✅ GOOD: Using $state and $derived
let count = $state(0);
let doubled = $derived(count * 2);

function increment() {
  count++;
}

// ❌ BAD: Old Svelte 4 patterns
import { writable } from "svelte/store";
const count = writable(0); // Only for shared state
```

**When to use:**

**In `.svelte` files:**

- `$state` — Component-local reactive variables
- `$derived` — Computed values (auto-update when dependencies change)
- `$effect` — Side effects (fetching data, subscriptions)
- `$props` — Component props (always type with `$props<Type>()`)

**In `.ts` files (plain modules):**

- `writable` / `readable` / `derived` from `svelte/store` — Shared state
- Runes don't work in `.ts` files (not compiled by Svelte)
- See "Part 3: Stores vs. Runes Boundary" for why

**Future (Svelte 5 universal reactivity):**

- `$state` will work in `.svelte.ts` files too
- We'll migrate all stores to `.svelte.ts` eventually
- For now, use stores for shared module-level state

---

## Part 11: API Client Best Practices

### 11.0 Browser Client Only ⚠️

**The `apiClient` in this section is for browser code only.** It uses `supabase.auth.getSession()`, which doesn't exist server-side.

**For server-side API calls in `+page.server.ts`**, see **Part 2.2.1: Server-Side API Calls**. Use `fetch` + token from `locals` instead.

### 11.1 Complete Client Implementation (Typed with ApiEndpoints)

```typescript
// frontend/src/lib/api/client.ts

import { supabase } from "$lib/supabase/client";
import type { ApiMethod, ApiRequest, ApiResponse } from "$lib/types/api";
import { ApiError } from "$lib/types/api";

export interface RequestOptions {
  responseType?: "json" | "blob" | "text";
  timeout?: number;
  headers?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  }

  private async getToken(): Promise<string> {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;

    if (!token) {
      throw new Error("Not authenticated");
    }

    return token;
  }

  /**
   * GET: Typed endpoints from ApiEndpoints map
   * Usage: await apiClient.get('/api/users/profile')
   */
  async get<T extends ApiMethod>(
    path: T,
    params?: Record<string, string | number | boolean>,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>>;

  /**
   * GET: Escape hatch for unknown endpoints
   * Usage: await apiClient.get<MyType>('https://external-api.com/data')
   */
  async get<T = unknown>(
    path: string,
    params?: Record<string, string | number | boolean>,
    options?: RequestOptions,
  ): Promise<T>;

  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean>,
    options?: RequestOptions,
  ): Promise<T> {
    const url = this.buildUrl(path, params);
    return this.request<T>("GET", url, undefined, options);
  }

  /**
   * POST: Typed endpoints from ApiEndpoints map
   * Usage: await apiClient.post('/api/chat', { message: 'Hello' })
   */
  async post<T extends ApiMethod>(
    path: T,
    body: ApiRequest<T>,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>>;

  /**
   * POST: Escape hatch for unknown endpoints
   * Usage: await apiClient.post<MyType>('/custom/endpoint', { data: ... })
   */
  async post<T = unknown>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T>;

  async post<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T> {
    return this.request<T>("POST", path, body, options);
  }

  /**
   * PUT: Typed endpoints from ApiEndpoints map
   */
  async put<T extends ApiMethod>(
    path: T,
    body: ApiRequest<T>,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>>;

  /**
   * PUT: Escape hatch for unknown endpoints
   */
  async put<T = unknown>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T>;

  async put<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<T> {
    return this.request<T>("PUT", path, body, options);
  }

  /**
   * DELETE: Typed endpoints from ApiEndpoints map
   */
  async delete<T extends ApiMethod>(
    path: T,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>>;

  /**
   * DELETE: Escape hatch for unknown endpoints
   */
  async delete<T = unknown>(path: string, options?: RequestOptions): Promise<T>;

  async delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", path, undefined, options);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {},
  ): Promise<T> {
    const token = await this.getToken();
    const url = new URL(path, this.baseUrl).toString();
    const { responseType = "json", timeout = 30000, headers = {} } = options;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw await this.parseError(response);
      }

      if (responseType === "blob") {
        return (await response.blob()) as T;
      }

      if (responseType === "text") {
        return (await response.text()) as T;
      }

      return response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      if (error instanceof TypeError) {
        throw new Error("Network error. Check your connection.");
      }

      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private async parseError(response: Response): Promise<ApiError> {
    let detail = response.statusText;
    let code = `HTTP_${response.status}`;

    try {
      const data = await response.json();
      detail = data.detail || detail;
      code = data.code || code;
    } catch {
      // Response wasn't JSON, use defaults
    }

    return new ApiError(response.status, code, detail);
  }

  private buildUrl(
    path: string,
    params?: Record<string, string | number | boolean>,
  ): string {
    const url = new URL(path, this.baseUrl);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }
}

export const apiClient = new ApiClient();
```

### 11.2 Type Safety: ApiEndpoints Enforcement

The ApiClient enforces the types defined in Part 1.4's ApiEndpoints map through method overloads.

**How it works:**

1. **Known Endpoints** (in ApiEndpoints map)

   ```typescript
   const response = await apiClient.post("/api/chat", { message: "Hello" });
   // ✅ path '/api/chat' is validated
   // ✅ body is validated: must have { message: string; conversation_id?: string }
   // ✅ response type is { message: string; citations: Citation[]; conversation_id: string }
   // ✅ IDE autocomplete works for all fields
   ```

2. **Unknown Endpoints** (escape hatch)
   ```typescript
   const response = await apiClient.post<MyType>("/custom/endpoint", {
     any: "data",
   });
   // ✅ path is not validated (any string allowed)
   // ✅ body is not validated (any shape allowed)
   // ✅ response type is MyType (explicit generic)
   // ⚠️ Use only for external APIs or development
   ```

**Type Error Examples:**

```typescript
// ❌ TYPE ERROR: Missing required field
await apiClient.post("/api/chat", {
  conversation_id: "123",
  // ERROR: 'message' is missing in type
});

// ❌ TYPE ERROR: Wrong field name
await apiClient.post("/api/chat", {
  msg: "Hello", // ERROR: 'msg' does not exist, did you mean 'message'?
});

// ❌ TYPE ERROR: Invalid path
await apiClient.get("/api/nonexistent", {});
// ERROR: Argument of type '/api/nonexistent' is not assignable to parameter of type ApiMethod

// ✅ CORRECT: All type checking passes
const response = await apiClient.post("/api/chat", {
  message: "Hello",
  conversation_id: "conv-123",
});
// response.message ✓
// response.citations ✓
// response.conversation_id ✓
```

**Adding New Endpoints:**

When you add a new API endpoint, follow this workflow:

1. **Add to ApiEndpoints in `lib/types/api.ts`**

   ```typescript
   export interface ApiEndpoints {
     '/api/chat': { ... };
     '/api/new-feature': {  // ← Add here
       request: { name: string; age: number };
       response: { id: string; created_at: string };
     };
   }
   ```

2. **Client automatically gets typed methods** (no code changes needed!)

   ```typescript
   // TypeScript automatically knows:
   const result = await apiClient.post("/api/new-feature", {
     name: "Alice",
     age: 30,
   });
   // result.id ✓
   // result.created_at ✓
   ```

3. **Add to backend API docs** (reference in CLAUDE.md or API docs)

**Rule: Always use known endpoints from ApiEndpoints.**

Use escape hatch only for:

- **External APIs** (outside your control, e.g., weather API, external CMS)
- **Ad-hoc development calls** (log as TODO: add to ApiEndpoints)
- **Temporary integration** (pending final API spec)

**Key Principle:**

Part 1.4's ApiEndpoints is not documentation—it's your **compile-time contract**. Add one type definition, get checking everywhere. This turns the map from "helpful reference" into actual guardrails that catch bugs during development.

---

## Part 12: Common Patterns & Pitfalls

### 12.1 Don't: Multiple API Calls Without Loading State

```typescript
// ❌ BAD
async function load() {
  messages = await fetchMessages();
  providers = await fetchProviders();
  // If first fetch fails, provider fetch never runs
}

// ✅ GOOD
async function load() {
  isLoading = true;
  try {
    [messages, providers] = await Promise.all([
      fetchMessages(),
      fetchProviders(),
    ]);
  } catch (err) {
    error = err.message;
  } finally {
    isLoading = false;
  }
}
```

### 12.2 Don't: Forget Auth in Form Handlers

```typescript
// ❌ BAD: No auth check
export const actions: Actions = {
  async chat({ request }) {
    const form = await superValidate(request, zod(schema));
    // User could be anyone!
  },
};

// ✅ GOOD: Auth check in locals
export const actions: Actions = {
  async chat({ request, locals }) {
    if (!locals.user) {
      return fail(401, { error: "Not authenticated" });
    }
    const form = await superValidate(request, zod(schema));
  },
};
```

### 12.3 Don't: Render HTML from User Input Without Sanitizing

```typescript
// ❌ BAD: XSS vulnerability
<div>{@html userInput}</div>

// ✅ GOOD: Escape or sanitize first
<div>{userInput}</div>

// ✅ GOOD: If you need HTML, sanitize first
import DOMPurify from 'dompurify';
<div>{@html DOMPurify.sanitize(userInput)}</div>
```

### 12.4 Don't: Store Secrets in Frontend Code

```typescript
// ❌ BAD
const OPENAI_KEY = "sk-xxx"; // Never in frontend!
const apiUrl = "https://api.example.com/secret";

// ✅ GOOD
const apiUrl = import.meta.env.VITE_API_BASE_URL; // Only public vars
// API key stays in backend, accessed via authenticated endpoint
```

### 12.5 Don't: Hardcode Credentials in Tests

```typescript
// ❌ BAD: Credentials in source code
test.beforeEach(async ({ page }) => {
  await page.fill('input[type="email"]', "testuser@example.com");
  await page.fill('input[type="password"]', "password123");
  await page.click('button:has-text("Sign In")');
});

// ✅ GOOD: Credentials from environment
test.beforeEach(async ({ page }) => {
  const username = process.env.TEST_USERNAME || "default@example.com";
  const password = process.env.TEST_PASSWORD || "default_password";

  await page.fill('input[type="email"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button:has-text("Sign In")');
});
```

Never commit test credentials. Use environment variables (`.env.test` in `.gitignore`) or a test account setup script. See Part 7.2 for test environment setup.

### 12.6 Don't: Use Browser apiClient in Server Actions

```typescript
// ❌ WRONG: apiClient doesn't work server-side
// frontend/src/routes/(app)/+page.server.ts

import { apiClient } from "$lib/api/client";

export const actions = {
  async chat({ request, locals }) {
    const form = await superValidate(request, zod(schema));

    // FAILS: apiClient.getToken() calls supabase.auth.getSession()
    // which only exists in the browser, not on the server
    const response = await apiClient.post("/api/chat", form.data);
  },
};

// ✅ CORRECT: Use fetch + token from locals
export const actions = {
  async chat({ request, locals }) {
    const form = await superValidate(request, zod(schema));

    if (!locals.token) {
      return fail(401, { error: "Not authenticated" });
    }

    const response = await fetch("http://localhost:8000/api/chat", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${locals.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(form.data),
    });

    return response.json();
  },
};
```

**Why?** The browser `apiClient` uses `supabase.auth.getSession()`, which only works in the browser. Server-side code needs a different approach: use the token from `locals` (set in `+layout.server.ts`) and call the API directly with `fetch`.

**Solution:** Either use raw `fetch` (as above) or create a `serverFetch` helper (see Part 2.2.1 for full implementation).

### 12.7 Don't: Use Interface + Object Literal for Errors

```typescript
// ❌ WRONG: Interface + object literal doesn't support instanceof checks

export interface ApiError extends Error {
  status: number;
  code: string;
}

// Object literal — not an instance of Error
const error: ApiError = {
  status: 404,
  code: "NOT_FOUND",
  message: "",
  name: "ApiError",
};

if (error instanceof ApiError) {
  // ❌ NEVER true with object literals
}

// ✅ CORRECT: Use a class

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  timestamp: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.timestamp = new Date().toISOString();
  }
}

// Now instanceof works
const error = new ApiError(404, "NOT_FOUND", "Not found");
if (error instanceof ApiError) {
  // ✅ TRUE — error is a real instance of ApiError
}
```

**Why:** Interfaces are TypeScript-only (erased at runtime). Object literals don't create class instances. Classes create actual runtime instances that `instanceof` can check.

Without a proper class:

- `instanceof` checks always fail
- Error handling bypasses specific status code handling (401, 429, etc.)
- Falls through to generic catch blocks
- Users see generic error messages instead of specific ones

---

## Part 13: Multi-Step Flows (Wizards)

**Reference Implementation:** Appointment Prep (`frontend/src/routes/(app)/appointment-prep/`)

This section documents the pattern for complex, multi-step flows with accumulated state, partial saves, error recovery, and back-navigation. Appointment Prep (5 steps, LLM integration, drag-and-drop) is the canonical example.

### 13.1 Architecture: Orchestrator + Steps Pattern

The multi-step flow uses a single orchestrator component that owns state and routes to step components via conditional rendering.

```typescript
// Step orchestrator owns ALL state for the flow
let state = $state({
  currentStep: 1 | 2 | 3 | 4 | 5,

  // Data accumulated across steps
  context: null,
  narrative: null,
  concerns: [],
  scenarios: [],

  // Shared error/loading for the entire flow
  error: null,
  isLoading: false,
});

// Render only the current step
{#if state.currentStep === 1}
  <Step1Component data={data.form} onNext={handleStep1} />
{:else if state.currentStep === 2}
  <Step2Component appointmentId={state.appointmentId} onNext={handleStep2} />
{/if}

// Navigation always in orchestrator
<button onclick={() => { if (state.currentStep > 1) state.currentStep--; }}>
  Back
</button>
```

**Why this pattern?**

- Single source of truth for all accumulated data
- Easy to persist, reset, or resume the entire state
- Steps are reusable (they don't own the state)
- Back-navigation is automatic (data persists)
- Entire flow state can be saved to sessionStorage

**Anti-pattern: Distributed state**

```typescript
// ❌ DON'T: State scattered across stores or component state
const step1Store = writable(null);
const step2Store = writable(null);
// This makes it hard to persist, serialize, or reset the entire flow
```

### 13.2 Type Safety for Multi-Step State

Define a single typed interface for the entire flow state:

```typescript
// lib/types/appointment.ts

export type AppointmentType =
  | "new_provider"
  | "existing_provider"
  | "telehealth";
export type AppointmentGoal =
  | "assess_status"
  | "explore_hrt"
  | "optimize_current_treatment";

export interface AppointmentContext {
  appointment_type: AppointmentType;
  goal: AppointmentGoal;
  dismissed_before: string;
  urgent_symptom: string | null;
}

export interface ScenarioCard {
  id: string;
  title: string;
  situation: string;
  suggestion: string;
  category: string;
}

export interface AppointmentPrepState {
  currentStep: 1 | 2 | 3 | 4 | 5;

  // Data accumulation
  appointmentId: string | null;
  context: AppointmentContext | null;
  narrative: string | null;
  concerns: string[];
  scenarios: ScenarioCard[];

  // Error/loading
  isLoading: boolean;
  error: string | null;
}
```

**Key pattern:** Use `1 | 2 | 3 | 4 | 5` for step numbers (literal union) to prevent invalid steps.

### 13.3 Initialize State and Handle Back-Navigation

```typescript
// In orchestrator (+page.svelte)

let state = $state<AppointmentPrepState>({
  appointmentId: null,
  context: null,
  narrative: null,
  concerns: [],
  scenarios: [],
  isLoading: false,
  error: null,
  currentStep: 1,
});

function goBack() {
  if (state.currentStep > 1) {
    state.error = null;
    state.currentStep = (state.currentStep - 1) as 1 | 2 | 3 | 4 | 5;
  }
}

function startOver() {
  state = {
    appointmentId: null,
    context: null,
    narrative: null,
    concerns: [],
    scenarios: [],
    isLoading: false,
    error: null,
    currentStep: 1,
  };
  sessionStorage.removeItem("appointmentPrepState");
}
```

**Key principle:** Back-navigation never validates or clears data. Users can freely explore earlier steps, and all data persists.

### 13.4 Individual Steps: Handle Their Own Loading/Error UI

Each step component manages its own UI state for long-running operations. Avoid propagating all errors to the parent.

```svelte
<!-- Step2Narrative.svelte: Generate LLM narrative -->

<script lang="ts">
  import { apiClient } from '$lib/api/client';
  import type { ApiError } from '$lib/types';

  let {
    appointmentId,
    onNext,
  }: {
    appointmentId: string;
    onNext: (narrative: string) => void;
  } = $props();

  let narrative = $state('');
  let isLoading = $state(true);
  let loadError = $state('');

  // Load narrative on mount
  $effect(() => {
    loadNarrative();
  });

  async function loadNarrative() {
    isLoading = true;
    loadError = '';
    try {
      const res = await apiClient.post(
        `/api/appointment-prep/${appointmentId}/narrative` as '/api/appointment-prep/{id}/narrative',
        { days_back: 60 }
      );
      narrative = res.narrative;
    } catch (e) {
      const msg =
        e instanceof Error && 'detail' in e
          ? (e as ApiError).detail
          : 'Failed to generate narrative. Please try again.';
      loadError = msg;
    } finally {
      isLoading = false;
    }
  }

  function handleNext() {
    onNext(narrative);
  }
</script>

<div class="mx-auto max-w-2xl space-y-6">
  {#if isLoading}
    <div class="flex flex-col items-center gap-4 p-8" role="status" aria-busy="true">
      <div class="h-8 w-8 animate-spin rounded-full border-4 border-teal-200 border-t-teal-600"></div>
      <p class="text-sm text-slate-500" aria-live="polite">
        Generating your symptom summary…
      </p>
    </div>
  {:else if loadError}
    <div class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
      {loadError}
      <button
        type="button"
        onclick={loadNarrative}
        class="ml-2 font-medium underline hover:no-underline"
      >
        Try again
      </button>
    </div>
  {:else}
    <textarea bind:value={narrative} rows="12" class="w-full rounded-xl border border-slate-200 px-4 py-3" />
    <button
      type="button"
      onclick={handleNext}
      disabled={!narrative.trim()}
      class="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-40"
    >
      Next: Prioritize your concerns
    </button>
  {/if}
</div>
```

**Pattern:**

- Step owns its local loading/error state
- Step calls parent `onNext()` when done (parent advances)
- Step never calls parent error handler for step-specific errors
- Step shows retry button locally for transient failures

### 13.5 Persist State Across Page Refreshes

For flows with expensive operations (LLM calls, drag-and-drop), save state to sessionStorage:

```typescript
// In orchestrator (+page.svelte)

let savedStateExists = $state(false);

// Load saved state on mount
$effect(() => {
  const saved = sessionStorage.getItem("appointmentPrepState");
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      state = parsed;
      savedStateExists = true;
    } catch (e) {
      console.error("Failed to restore appointment prep state:", e);
      savedStateExists = false;
    }
  }
});

// Save state whenever it changes
$effect(() => {
  sessionStorage.setItem("appointmentPrepState", JSON.stringify(state));
});
```

**Resume dialog (optional):**

Show users the option to resume if they return mid-flow:

```svelte
{#if savedStateExists && state.currentStep > 1}
  <div role="dialog" class="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h3 class="font-semibold text-blue-900">Resume Previous Session?</h3>
        <p class="mt-1 text-sm text-blue-700">
          We found your previous appointment prep session at Step {state.currentStep}.
          You can continue where you left off or start fresh.
        </p>
      </div>
      <div class="flex flex-shrink-0 gap-2">
        <button
          type="button"
          onclick={() => (savedStateExists = false)}
          class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Resume
        </button>
        <button
          type="button"
          onclick={() => {
            sessionStorage.removeItem('appointmentPrepState');
            startOver();
            savedStateExists = false;
          }}
          class="rounded-lg border border-blue-600 px-3 py-2 text-sm font-semibold text-blue-600 hover:bg-blue-50"
        >
          Start Fresh
        </button>
      </div>
    </div>
  </div>
{/if}
```

### 13.6 Error Recovery (Retry Without Data Loss)

If a step's API call fails (timeout, network error), keep the user in the failing step with a retry button. Don't force them backward.

```typescript
// Step 2 fails with "Timeout generating narrative"
// User sees:
// ✅ Error message with specific problem
// ✅ "Try Again" button in the step
// ✅ Data from Step 1 still intact
// ✅ User clicks "Try Again" → retries narrative generation
// ✅ No need to go back to Step 1
```

The key: **Retry at the step level, never force backward navigation on failure.**

### 13.7 Progress Indicator

Show the user their position in the flow with a progress bar and step counter:

```svelte
<div class="border-b border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-slate-900">Appointment Prep</h1>
      <p class="mt-0.5 text-sm text-slate-500">
        Step {state.currentStep} of 5: {STEP_TITLES[state.currentStep]}
      </p>
    </div>
    {#if state.currentStep > 1}
      <button
        type="button"
        onclick={goBack}
        class="rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100"
        aria-label="Go back to previous step"
      >
        ← Back
      </button>
    {/if}
  </div>

  <!-- Progress bar -->
  <div
    class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
    role="progressbar"
    aria-valuenow={state.currentStep}
    aria-valuemin={1}
    aria-valuemax={5}
    aria-label="Step {state.currentStep} of 5"
  >
    <div
      class="h-full rounded-full bg-teal-500 transition-all duration-500"
      style="width: {(state.currentStep / 5) * 100}%"
    ></div>
  </div>
</div>
```

### 13.8 Multi-Step Checklist

When building a wizard, verify:

- [ ] Define typed `State` interface with literal union for step numbers (`1 | 2 | 3 | 4 | 5`)
- [ ] Use single orchestrator component that owns all state
- [ ] Render only current step via `{#if state.currentStep === N}`
- [ ] Back-navigation always allowed (data always preserved)
- [ ] Each step handles its own loading/error UI with retry buttons
- [ ] Show progress indicator (bar + step counter)
- [ ] Persist state to `sessionStorage` for long flows (especially LLM calls)
- [ ] Handle timeouts/network errors with retry (don't force backward)
- [ ] Clear state on completion (or offer to resume)
- [ ] Test: Refresh browser mid-flow → state restores
- [ ] Test: Go back from Step 4 to Step 2 → edit → go forward again
- [ ] Test: All steps render correctly and data accumulates
- [ ] Accessibility: All buttons have `aria-label`, progress bar has ARIA attributes

**Reference:** `frontend/src/routes/(app)/appointment-prep/` — Full working example with 5 steps, LLM integration, drag-and-drop reordering, and sessionStorage persistence.

---

## Part 14: Svelte Transitions & Animations

### 14.1 Transition Basics

Svelte transitions animate elements entering (`in:`) and leaving (`out:`) the DOM. Use them for:

- Cards/items being added or removed
- Modals and overlays appearing/disappearing
- Success messages and alerts
- Loading skeletons being replaced with content
- Form state changes

**Do NOT use transitions for:**
- Hover effects (use CSS instead)
- Loading spinners (use CSS rotation)
- Animated values (use `$derived` + CSS transitions)

**Basic Syntax:**

```svelte
<script>
	import { fly, fade, scale } from 'svelte/transition';
	import { flip } from 'svelte/animate';

	let visible = $state(true);
</script>

<!-- Fade in/out -->
{#if visible}
	<div in:fade out:fade>
		Content
	</div>
{/if}

<!-- Fly in from the left, out upward -->
{#if visible}
	<div in:fly={{ x: -20, duration: 200 }} out:fly={{ y: -20, duration: 150 }}>
		Animated item
	</div>
{/if}

<!-- Combined with animate:flip for reordering -->
{#each items as item (item.id)}
	<div in:fly={{ x: -20 }} out:fly={{ x: 20 }} animate:flip={{ duration: 200 }}>
		{item.name}
	</div>
{/each}
```

### 14.2 Common Transitions

**Fade:** Subtle opacity change, good for replacing content or showing/hiding UI

```svelte
<div in:fade={{ duration: 150 }} out:fade={{ duration: 100 }}>
	Content fades in/out
</div>
```

**Fly:** Elements enter/exit from a direction, creates directional movement

```svelte
<!-- Enter from left, exit upward -->
<div in:fly={{ x: -20, duration: 200 }} out:fly={{ y: -20, duration: 150 }}>
	Flies in/out
</div>
```

**Scale:** Elements grow/shrink, good for modals or emphasis

```svelte
<div in:scale={{ duration: 200 }} out:scale={{ duration: 150 }}>
	Appears with scale animation
</div>
```

**Flip Animation (on reorder):** Smoothly reorders list items when array changes

```svelte
{#each items as item (item.id)}
	<div animate:flip={{ duration: 200 }}>
		{item.name}
	</div>
{/each}
```

### 14.3 Duration Guidelines

- **Quick feedback (dismiss, success):** 150ms
- **Entry animations (cards, modals):** 200ms
- **Exit animations:** 100-150ms (faster feels more responsive)
- **Reordering (animate:flip):** 200-300ms (longer looks smoother)
- **Stagger multiple items:** Add delay on each (e.g., `delay: i * 50`)

**Why these times:**
- < 100ms: Too fast, feels jarring
- 100-200ms: Snappy, responsive, most common
- 200-300ms: Smooth, deliberate, for complex animations
- > 300ms: Slow, feels sluggish (except reordering)

### 14.4 Accessibility with Transitions

**Always ensure transitions don't break accessibility:**

```svelte
<!-- ✅ GOOD: Alert animates in but aria-live announces immediately -->
{#if showSuccess}
	<div
		in:fly={{ y: -20, duration: 200 }}
		role="alert"
		aria-live="polite"
		aria-label="Success message"
	>
		Your data was saved!
	</div>
{/if}

<!-- ✅ GOOD: Dismiss button always present, aria-label clear -->
<button
	aria-label="Dismiss card"
	onclick={() => dismissCard(card.id)}
	class="h-10 w-10"
>
	<X size={20} />
</button>

<!-- ❌ BAD: Content hidden via transition, screen readers announce nothing -->
{#if visible}
	<!-- No aria-live, no role -->
	<div in:fade>Content</div>
{/if}
```

**Key Rules:**
- Dynamic messages: Use `role="alert"` + `aria-live="polite"`
- Dismiss buttons: Use `aria-label` (always 44×44px minimum)
- Modals: Auto-focus on open, return focus on close
- Spinners: Use `aria-busy="true"` on container

### 14.5 Animation Config Constants

For consistency across your app, define animation constants:

```typescript
// frontend/src/lib/config/animations.ts

export const ANIMATION_DURATION = {
	quick: 150,    // Dismiss, quick feedback
	standard: 200, // Cards entering, standard animations
	slow: 300,     // Reordering, complex movements
} as const;

export const ANIMATION_EASING = {
	in: 'cubic-bezier(0.4, 0, 1, 1)',     // Ease in
	out: 'cubic-bezier(0, 0, 0.2, 1)',    // Ease out
	inOut: 'cubic-bezier(0.4, 0, 0.2, 1)', // Ease in/out
} as const;
```

Then use throughout:

```svelte
<script>
	import { ANIMATION_DURATION, ANIMATION_EASING } from '$lib/config/animations';
</script>

<div
	in:fly={{ x: -20, duration: ANIMATION_DURATION.standard }}
	out:fly={{ y: -20, duration: ANIMATION_DURATION.quick }}
>
	Consistently timed animation
</div>
```

### 14.6 Symptom Logging: Actual Implementation

**File:** `frontend/src/routes/(app)/log/+page.svelte`

The symptom logging component uses Svelte transitions effectively and serves as a real-world example of the patterns in this section.

**What it does right:**
- Uses `fly` and `fade` transitions appropriately for entering/exiting UI
- Short durations (150-200ms) create snappy, responsive feel
- Cards exit upward when dismissed, chips slide in from left
- Empty state uses `fade` for subtle appearance
- Success message uses `fly` for attention-drawing
- Error messages animate in with `fly`
- Full accessibility support (aria-labels, role="alert", aria-live)

**What could be improved (deferred to post-launch polish):**
- Timing is inconsistent (mix of 150ms, 200ms, 300ms) — should use centralized constants
- Missing `animate:flip` on card grid — when a card is dismissed, others should smoothly reorder
- No easing curves — all transitions use linear by default, should use cubic-bezier for smoother feel
- Dismiss button is 24px × 24px (below 44px accessibility minimum)

**Post-launch polish:** See `docs/planning/V2_V3_ROADMAP.md` under "Symptom Logging Animation Polish"

**Reference for your own implementations:** Study this component to see how transitions work in practice with real data flow and state management.

### 14.7 Common Patterns & Gotchas

**Pattern: Staggered List Items**

```svelte
{#each items as item, i (item.id)}
	<div
		in:fly={{ x: -20, duration: 200, delay: i * 50 }}
		out:fly={{ x: 20, duration: 100 }}
	>
		{item.name}
	</div>
{/each}
```

**Gotcha: Transitions + Conditional Content**

```svelte
<!-- ❌ BAD: Transition never fires (element never leaves DOM) -->
{#if show}
	<div in:fly out:fly>Content</div>
{/if}

<!-- ✅ GOOD: Block transitions when content changes -->
{#key contentId}
	<div in:fade out:fade>Content updated</div>
{/key}
```

**Gotcha: Transitions + Data Binding**

```svelte
<!-- ❌ BAD: Transition conflicts with bound value changes -->
<input
	value={name}
	in:fly={{ y: -20, duration: 200 }}
/>

<!-- ✅ GOOD: Transition only on entry/exit, not on data changes -->
{#if showInput}
	<input bind:value={name} in:fly={{ y: -20 }} out:fly={{ y: -20 }} />
{/if}
```

### 14.8 Transitions Checklist

When adding transitions:

- [ ] **Purpose clear:** Animation explains what's happening (enter/exit, emphasis)
- [ ] **Duration appropriate:** 150-200ms for most, not > 300ms (except reordering)
- [ ] **Not overused:** Only on significant state changes, not micro-interactions
- [ ] **Accessibility verified:** aria-live on alerts, aria-label on buttons, 44px targets
- [ ] **Mobile tested:** Animations smooth on slower devices (test on real phone or DevTools throttle)
- [ ] **Easing added:** Use cubic-bezier, not linear (if using config constants, consistent across app)
- [ ] **No conflicts:** CSS transitions don't overlap with Svelte transitions
- [ ] **Tested with reduced motion:** `prefers-reduced-motion` should skip or speed up animations

---

## Summary Checklist

Every time you add frontend code, verify:

- [ ] **Types:** All props, API responses, and state are typed
- [ ] **State Management:** Runes in `.svelte` files, stores in `.ts` files (see Part 3)
- [ ] **Validation:** Forms validated with Zod + Superforms server-side
- [ ] **Forms:** Server actions validate input, use `fetch` + token from locals for API calls (not browser `apiClient`), see Part 2.2.1
- [ ] **Error Handling:** Route errors in `+error.svelte`, component errors in try/catch + state (see Part 4)
- [ ] **Loading States:** Isloading pattern + UI feedback (spinner/skeleton)
- [ ] **Accessibility:** Semantic HTML, ARIA labels, 44×44px targets, keyboard nav
- [ ] **Responsive:** Tested at 375px, 667px, 768px, 1440px with no overflow
- [ ] **Tests:** Unit tests for utilities, component tests for UI, e2e for flows
- [ ] **Security:** No XSS, no hardcoded secrets, auth checks in actions
- [ ] **Performance:** No unnecessary re-renders (proper $derived usage)
- [ ] **Documentation:** JSDoc on public components/functions
- [ ] **Multi-Step Flows:** State owned by orchestrator, validation before advancing, error recovery with retry, sessionStorage persistence (see Part 13)

---

## Resources

- **SvelteKit Docs:** https://kit.svelte.dev/docs
- **Svelte 5 Runes:** https://svelte-5-preview.vercel.app/docs/runes
- **shadcn-svelte:** https://shadcn-svelte.com
- **Superforms:** https://superforms.rocks
- **Zod:** https://zod.dev
- **Testing Library:** https://testing-library.com
- **Playwright:** https://playwright.dev
- **WCAG 2.1:** https://www.w3.org/WAI/WCAG21/quickref/
