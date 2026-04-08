---
name: testing-discipline
description: >
  Use when implementing any feature, bugfix, or refactor. Enforces honest testing
  practices across a mono repo with a FastAPI/Supabase backend and Svelte/TypeScript
  frontend. Prioritizes tests that prove behavior over tests that confirm implementation.
when_to_use: >
  Any time code is being written, modified, or reviewed. Activates for new features,
  bug fixes, refactoring, and code review.
version: 1.0.0
languages: [python, typescript, svelte]
---

# Testing Discipline

## The Core Problem This Skill Solves

When the same AI session writes code AND tests, the tests tend to be tautological —
they verify what was built, not what was required. This skill exists to break that cycle.

**The question is never "does my code work?" It's "would this test catch the bug?"**

## Golden Rule

```
Every test must be able to fail for a meaningful reason.
If you can't describe a realistic bug this test would catch, the test is worthless.
```

Before writing any test, state in a comment:

```python
# CATCHES: [description of a realistic bug this test would detect]
```

If you can't fill in the blank, don't write the test.

## Decision: New Code vs. Existing Code

```
Is this NEW code or a CHANGE to existing code?

NEW CODE ──────► Write test first (TDD).
                 Watch it fail.
                 Implement minimally.
                 See "TDD for New Code" below.

EXISTING CODE ─► Write characterization test first.
                 Prove current behavior.
                 THEN write failing test for new behavior.
                 See "Changing Existing Code" below.
```

---

## TDD for New Code

For any new function, endpoint, or component: write the test before the implementation.

### The Cycle

1. **RED** — Write one test describing desired behavior. Run it. Watch it fail.
2. **Verify RED** — Confirm it fails because the feature is missing, not because of a typo or import error.
3. **GREEN** — Write the minimum code to make the test pass. Nothing more.
4. **Verify GREEN** — Run the test. Run the full suite. Everything green.
5. **REFACTOR** — Clean up. Keep tests green. Don't add behavior.
6. **Repeat** — Next behavior, next test.

### The Iron Law (New Code Only)

```
No implementation code without a failing test first.
```

Wrote implementation before the test? Don't retrofit tests onto it.
Delete the implementation. Write the test. Watch it fail. Reimplement.

This sounds extreme but it's the only way to know your test actually tests something.

---

### When TDD Feels Impossible

Sometimes you can't write the test first because a dependency doesn't exist yet —
a repository method, a service interface, a provider ABC. This is not an excuse
to skip TDD. It's a signal to build the interface first.

**The pattern:**

1. Define the interface (ABC or stub) for the missing dependency
2. Write the test against that interface using a mock
3. Watch the test fail
4. Implement the real dependency
5. Watch the test pass

```python
# Scenario: you're writing SymptomService but SymptomRepository doesn't exist yet.
# Don't implement the service without tests. Define the interface first.

# Step 1 — stub the interface (no implementation yet)
class SymptomRepositoryBase(ABC):
    @abstractmethod
    async def get_by_user(self, user_id: str) -> list[SymptomLog]: ...

# Step 2 — write the test against the interface
# CATCHES: Service returns all symptoms without filtering to the requesting user,
#          leaking another user's health data
async def test_get_symptoms_filters_by_user():
    mock_repo = AsyncMock(spec=SymptomRepositoryBase)
    mock_repo.get_by_user.return_value = [
        SymptomLog(id="1", user_id="user-abc", symptom="fatigue")
    ]
    service = SymptomService(repo=mock_repo)

    results = await service.get_symptoms(user_id="user-abc")

    mock_repo.get_by_user.assert_called_once_with(user_id="user-abc")
    assert all(r.user_id == "user-abc" for r in results)

# Step 3 — run it, watch it fail (SymptomService doesn't exist yet)
# Step 4 — implement SymptomRepository and SymptomService
# Step 5 — run it, watch it pass
```

**The rule:** if you're blocked on TDD because something doesn't exist,
define its interface and test against that. You should never be in a position
where "the dependency doesn't exist yet" justifies skipping the failing test step.

**One exception:** if you're writing a pure utility function with no dependencies,
just write the test directly — no interface needed. Utils have no collaborators
to stub.

## Changing Existing Code

For code that already exists and is working, rewriting everything test-first
isn't always practical. Use characterization testing before making changes.

### Steps

1. **Characterize** — Write a test that captures the current behavior, even if you think
   the behavior is wrong. Run it. It should pass.
2. **Specify** — Write a new test for the desired behavior change. Run it. It should fail.
3. **Implement** — Change the code to make the new test pass.
4. **Verify** — Both the characterization test (if behavior should be preserved) and the
   new test should pass. If the characterization test now fails, that's expected only if
   you're intentionally changing that behavior — and you should be explicit about it.

### Why This Matters

Characterization tests protect you from accidentally breaking things that work.
In a codebase largely written by AI, there may be implicit behaviors you don't know about.
Characterize first, then change.

---

## Backend Rules (FastAPI + Supabase + pgvector + OpenAI)

### The Mock Problem

This codebase has 80%+ coverage but much of it tests mocks, not behavior.
A test that verifies `supabase.from('table').select()` was called with the right
arguments doesn't tell you the query logic is correct.

**Rules for mocking:**

```
MOCK ONLY WHAT YOU DON'T OWN.

External services (Supabase, OpenAI API calls) ──► Mock at the boundary
Your own functions and classes ──────────────────► Do not mock. Use the real thing.
Database queries ────────────────────────────────► Prefer a test database over mocking
```

### What to Test at Each Layer

**API Endpoints (routes):**

- Use `httpx.AsyncClient` with the real FastAPI app
- Test request → response (status code, response shape, error cases)
- Mock only the external service calls (Supabase client, OpenAI client)
- Test auth/permission behavior, not just happy paths

```python
# CATCHES: Endpoint returns 200 with malformed body when validation should reject it
async def test_create_item_rejects_empty_name(client: httpx.AsyncClient):
    response = await client.post("/items", json={"name": ""})
    assert response.status_code == 422
```

**Business Logic (services, utils):**

- Test with real inputs and outputs
- No mocking your own code
- Focus on edge cases, boundary conditions, error states

```python
# CATCHES: Chunking function silently drops the last chunk when text length
#          isn't evenly divisible by chunk_size
def test_chunk_text_preserves_all_content():
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=300)
    assert "".join(chunks) == text
```

**OpenAI / LLM Integration:**

- Mock the API call itself, but test everything around it
- Test prompt construction with real inputs
- Test response parsing with realistic (but static) response fixtures
- Test error handling (rate limits, timeouts, malformed responses)
- Do NOT test that the LLM "returns the right answer" — that's not deterministic

```python
# CATCHES: Embedding function crashes on empty string input instead of
#          returning a zero vector or raising a clear error
async def test_get_embedding_handles_empty_string(mock_openai):
    mock_openai.embeddings.create.return_value = mock_embedding_response([0.0] * 1536)
    result = await get_embedding("")
    assert len(result) == 1536
```

**pgvector / Similarity Search:**

- Test that your query construction is correct
- Test result ranking/filtering logic with known test data
- Test edge cases: no results, identical scores, empty query vectors

### pgvector / Similarity Search

The RAG pipeline is central to Meno. These tests are not optional.

**What to test:**

- Query construction produces the correct similarity threshold and top-k limit
- Results are returned in descending similarity order
- Filtering by metadata (source, date range, chunk type) works correctly
- Edge cases: empty result set, single result, all results tied on score

```python
# CATCHES: Similarity search returns chunks in wrong order because ORDER BY
#          was accidentally dropped during a query refactor
async def test_similarity_search_returns_results_in_score_order(mock_supabase):
    chunks = [
        {"id": "a", "content": "high relevance", "similarity": 0.92},
        {"id": "b", "content": "medium relevance", "similarity": 0.75},
        {"id": "c", "content": "low relevance", "similarity": 0.61},
    ]
    setup_supabase_response(mock_supabase, data=chunks)

    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=3)

    assert [r.id for r in results] == ["a", "b", "c"]
    assert results[0].similarity > results[1].similarity > results[2].similarity


# CATCHES: top_k parameter is ignored, returning all chunks and blowing
#          the context window
async def test_similarity_search_respects_top_k(mock_supabase):
    chunks = [{"id": str(i), "similarity": 0.9 - i * 0.01} for i in range(20)]
    setup_supabase_response(mock_supabase, data=chunks)

    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=5)

    assert len(results) == 5


# CATCHES: Source filter is silently ignored, returning chunks from all
#          sources when only PubMed chunks were requested
async def test_similarity_search_filters_by_source(mock_supabase):
    setup_supabase_response(mock_supabase, data=[
        {"id": "1", "source": "pubmed", "similarity": 0.88},
    ])

    results = await rag_repo.similarity_search(
        query_vector=[0.1] * 1536,
        top_k=5,
        source_filter="pubmed",
    )

    assert all(r.source == "pubmed" for r in results)


# CATCHES: Empty result set raises an exception instead of returning
#          an empty list, breaking the RAG pipeline silently
async def test_similarity_search_returns_empty_list_when_no_results(mock_supabase):
    setup_supabase_response(mock_supabase, data=[])

    results = await rag_repo.similarity_search(query_vector=[0.1] * 1536, top_k=5)

    assert results == []
```

**Mutation notes for the above:** these tests would catch: `ORDER BY similarity DESC`
becoming `ASC`; `top_k` parameter never applied to the query; source filter
applied with wrong column name; empty result raising `IndexError` instead of
returning `[]`.

### Backend Anti-Patterns (Stop Doing These)

| Pattern                                              | Problem                                 | Instead                                               |
| ---------------------------------------------------- | --------------------------------------- | ----------------------------------------------------- |
| Mocking your own service classes                     | Tests prove nothing about real behavior | Call the real service with mocked externals           |
| `assert mock.called_with(...)` as the only assertion | Tests the call, not the result          | Assert on the return value or side effect             |
| Fixtures that duplicate implementation logic         | Test is tautological                    | Use simple, static test data                          |
| One test per endpoint, happy path only               | Misses validation, auth, edge cases     | Test error cases, auth failures, bad input            |
| `@pytest.mark.parametrize` with 20 trivial cases     | Coverage theater                        | Parametrize only when cases test different code paths |

---

## Frontend Rules (Svelte + TypeScript)

### Starting From Zero

This frontend has almost no tests. Don't try to retroactively test everything.
Instead, adopt a "test on touch" policy:

```
Building a new component?  ──► Write tests (TDD).
Modifying a component?     ──► Add tests for the behavior you're changing.
Fixing a bug?              ──► Write a failing test that reproduces it.
Not touching it?           ──► Leave it alone for now.
```

### Recommended Setup

- **Vitest** as test runner (fast, native TypeScript, Vite-compatible)
- **@testing-library/svelte** for component tests
- **jsdom** or **happy-dom** as the DOM environment

### What to Test

**Components:** Test from the user's perspective. Render the component, interact with it
the way a user would, assert on what appears in the DOM.

```typescript
// CATCHES: Submit button fires even when required fields are empty
test("disables submit when name field is empty", async () => {
  render(ItemForm);
  const submitButton = screen.getByRole("button", { name: /submit/i });
  expect(submitButton).toBeDisabled();

  await userEvent.type(screen.getByLabelText(/name/i), "Test Item");
  expect(submitButton).toBeEnabled();
});
```

**Stores / State Logic:** Test the logic, not the reactivity mechanism.

```typescript
// CATCHES: Filter function includes archived items in "active" view
test("activeItems excludes archived items", () => {
  const store = createItemStore([
    { id: 1, name: "Active", archived: false },
    { id: 2, name: "Gone", archived: true },
  ]);
  expect(get(store.activeItems)).toHaveLength(1);
  expect(get(store.activeItems)[0].name).toBe("Active");
});
```

**API Client / Fetch Wrappers:** Mock fetch, test your wrapper's behavior.

```typescript
// CATCHES: API client doesn't include auth token after login state changes
test("includes auth header when user is authenticated", async () => {
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

### Frontend Anti-Patterns

| Pattern                                       | Problem                             | Instead                                        |
| --------------------------------------------- | ----------------------------------- | ---------------------------------------------- |
| Testing component internals / state variables | Brittle, breaks on refactor         | Test what the user sees and does               |
| Snapshot tests on large components            | Always break, nobody reads the diff | Test specific behaviors                        |
| `getByTestId` everywhere                      | Tests don't reflect user experience | Use `getByRole`, `getByLabelText`, `getByText` |
| Testing Svelte reactivity mechanics           | Tests the framework, not your code  | Test inputs → visible outputs                  |

---

## The Self-Confirmation Problem

This is the #1 risk when AI writes both code and tests in the same session.

### How to Catch It

After Claude writes tests for new code, apply this check:

```
For each test, ask:
  1. Could this test pass with a WRONG implementation?
  2. If I introduced [specific realistic bug], would this test catch it?
  3. Does this test assert on BEHAVIOR or on IMPLEMENTATION DETAILS?
```

If the answer to #1 is yes, the test needs to be stronger.
If the answer to #2 is no, the test is missing something.
If the answer to #3 is "implementation details," rewrite it.

### Practical Technique: The Mutation Check

After writing tests for a piece of code, mentally (or actually) introduce a bug:

- Off-by-one in a loop
- Swapped conditional (`>` instead of `>=`)
- Missing null check
- Wrong variable in a return statement

Would the tests catch it? If not, they're confirming the implementation, not guarding behavior.

**Claude: when you write tests, include a brief "mutation note" in your response
listing 2-3 specific bugs these tests would catch. If you can't list any, the tests
aren't good enough.**

---

## Integration with Compound Engineering

This skill works alongside the CE plugin workflow. The commands below
are explicit activation points — when invoked, apply the corresponding
rules from this skill without being asked.

- **`/ce:plan`** — Before writing any code, state which testing approach
  applies (TDD for new code, characterization for existing code) and why.
  Include test strategy in the plan. This step is non-negotiable.

- **`/ce:work`** — **This skill is active.** No implementation without a
  failing test first (new code) or characterization test (existing code).
  Apply all rules above. Include CATCHES: comments on every test.

- **`/ce:review`** — Explicitly check for: mock-heavy tests, missing
  CATCHES: comments, tests that assert on implementation details rather
  than behavior, and the self-confirmation problem. Surface findings
  even if minor — silence in review is not a pass.

- **`/ce:compound`** — Document any new testing patterns, fixtures, or
  helpers that emerged. Add them to the project's testing utilities so
  the next session benefits from them.

---

## Quick Reference

```
NEW CODE        → TDD (test first, watch fail, implement, watch pass)
EXISTING CODE   → Characterize current behavior, then test-first for changes
BACKEND MOCKS   → Mock only what you don't own (Supabase, OpenAI)
FRONTEND TESTS  → Test on touch. User perspective. No snapshots.
EVERY TEST      → Must have a "CATCHES:" comment explaining what bug it detects
AI-WRITTEN CODE → Include mutation notes. Challenge test quality in review.
```
