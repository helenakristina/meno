---
paths:
  - frontend/src/lib/schemas/**/*.ts
  - frontend/src/lib/types/**/*.ts
---

# Types and Schemas Rules

## Types (`src/lib/types/`)

One domain per file (`chat.ts`, `symptoms.ts`, etc.). Export everything from `index.ts`.
Use `interface` for object shapes. Include state types alongside domain types.

```typescript
// src/lib/types/symptoms.ts
export interface SymptomLog {
  id: string;
  userId: string;
  symptomId: string;
  severity: 1 | 2 | 3 | 4 | 5;
  loggedAt: string;
  notes?: string;
}

export interface SymptomLogState {
  logs: SymptomLog[];
  isLoading: boolean;
  error: string | null;
}
```

## API Types (`src/lib/types/api.ts`)

All backend endpoints must be defined in the `ApiEndpoints` interface.
The typed API client validates paths, request bodies, and response types at compile time.

Add to `ApiEndpoints` first. The client gets type checking automatically.
Use the escape hatch (`apiClient.post<MyType>(...)`) only for external APIs.

## ApiError

`ApiError` must be a class extending `Error`, not an interface + object literal.
`instanceof` checks fail at runtime on plain objects.

```typescript
// YES
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// NO — instanceof ApiError always returns false
export interface ApiError {
  message: string;
  status: number;
}
```

## Schemas (`src/lib/schemas/`)

One Zod schema per form. Export both the schema and its inferred type.

```typescript
// src/lib/schemas/symptom-log.ts
import { z } from "zod";

export const symptomLogSchema = z.object({
  symptomId: z.string().uuid(),
  severity: z.number().int().min(1).max(5),
  notes: z.string().max(500).optional(),
});

export type SymptomLogSchema = z.infer<typeof symptomLogSchema>;
```

## No Implicit Any

TypeScript strict mode is on. No `any`. No `as any`. If you need an escape,
use `unknown` and narrow with a type guard.
