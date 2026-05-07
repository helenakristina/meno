---
paths:
  - frontend/src/**/+page.server.ts
  - frontend/src/**/+layout.server.ts]
---

# Server Action Rules

## Critical: Browser Client vs Server Context

Getting this wrong causes silent auth failures. There is no runtime error —
the request simply fails to authenticate.

| Context                        | Use                                 | Token source                 |
| ------------------------------ | ----------------------------------- | ---------------------------- |
| `.svelte` components (browser) | `apiClient` from `$lib/api/client`  | `supabase.auth.getSession()` |
| `+page.server.ts` actions      | `fetch()` or `serverFetch()` helper | `locals.token`               |
| `+layout.server.ts`            | `fetch()` or `serverFetch()` helper | `locals.token`               |

**Never import `apiClient` in server files.** It calls `supabase.auth.getSession()`
which does not exist in the server context.

## Every Server Action Must

1. Check `locals.user` — reject immediately if not authenticated
2. Use `locals.token` for the Authorization header
3. Use `SECRET_API_BASE_URL` (not `PUBLIC_VITE_API_BASE_URL`)
4. Return typed responses using SvelteKit `fail()` for errors

```typescript
// +page.server.ts
import { fail } from "@sveltejs/kit";
import type { Actions } from "./$types";

export const actions: Actions = {
  submit: async ({ request, locals, fetch }) => {
    // Step 1: auth check — always first
    if (!locals.user || !locals.token) {
      return fail(401, { error: "Unauthorized" });
    }

    const data = await request.formData();

    // Step 2: use locals.token, SECRET_API_BASE_URL
    const response = await fetch(`${SECRET_API_BASE_URL}/api/items`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${locals.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(Object.fromEntries(data)),
    });

    if (!response.ok) {
      return fail(response.status, { error: "Request failed" });
    }

    return { success: true };
  },
};
```

## Environment Variables

| Variable                   | Context      | Use for                       |
| -------------------------- | ------------ | ----------------------------- |
| `SECRET_API_BASE_URL`      | Server only  | Backend URL in server actions |
| `PUBLIC_VITE_API_BASE_URL` | Browser safe | Backend URL in browser client |

Never use `PUBLIC_VITE_` variables in server files. Never use `SECRET_` variables
in `.svelte` files or `client.ts`.
