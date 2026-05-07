---
paths:
  - frontend/src/**/*.test.ts
  - frontend/src/**/*.spec.ts
---

# Frontend Test Rules

## Test on Touch Policy

This frontend has limited test coverage. Do not try to retroactively test everything.

```
Building a new component?  → Write tests (TDD)
Modifying a component?    → Add tests for the behavior you're changing
Fixing a bug?             → Write a failing test that reproduces it first
Not touching it?          → Leave it alone for now
```

## Test From the User's Perspective

Use `@testing-library/svelte`. Interact the way a user would. Assert on what appears
in the DOM. Never test Svelte internals or component state variables directly.

```typescript
// CATCHES: Submit fires even when required fields are empty
test("disables submit when name field is empty", async () => {
  render(ItemForm);
  const btn = screen.getByRole("button", { name: /submit/i });
  expect(btn).toBeDisabled();

  await userEvent.type(screen.getByLabelText(/name/i), "Test");
  expect(btn).toBeEnabled();
});
```

## Selectors — Priority Order

1. `getByRole` — matches what accessibility tools see
2. `getByLabelText` — matches how users find form fields
3. `getByText` — matches visible text
4. `getByTestId` — last resort only, and only if the others genuinely can't work

## API Client Tests

Mock `fetch`, test the wrapper behavior:

```typescript
// CATCHES: Auth token not included after session state changes
test("includes auth header when authenticated", async () => {
  const mockFetch = vi.fn().mockResolvedValue(new Response("{}"));
  const client = createApiClient({ fetch: mockFetch, token: "test-token" });
  await client.get("/items");
  expect(mockFetch).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
    }),
  );
});
```

## File Naming

- `feature.test.ts` — unit and component tests (Vitest)
- `feature.spec.ts` — E2E tests (Playwright)

## Anti-Patterns

| Pattern                             | Problem                            | Instead                       |
| ----------------------------------- | ---------------------------------- | ----------------------------- |
| Testing component state variables   | Brittle, breaks on refactor        | Test what the user sees       |
| Snapshot tests on large components  | Always break, nobody reads diffs   | Test specific behaviors       |
| `getByTestId` everywhere            | Doesn't reflect user experience    | `getByRole`, `getByLabelText` |
| Testing Svelte reactivity mechanics | Tests the framework, not your code | Test inputs → visible outputs |
