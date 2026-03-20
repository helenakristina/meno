# Testing Anti-Patterns Reference

Companion to the `testing-discipline` skill. Consult when reviewing tests or when
test quality is in question.

## The Tautological Test

**What it looks like:**
```python
def test_get_user(mock_supabase):
    mock_supabase.from_("users").select("*").eq("id", 1).execute.return_value = {
        "data": [{"id": 1, "name": "Alice"}]
    }
    result = get_user(1)
    assert result == {"id": 1, "name": "Alice"}
```

**Why it's worthless:** The test returns exactly what the mock returns. It proves the
function passes data through. It would pass even if `get_user` ignored its argument
entirely and just returned whatever Supabase returned.

**Fix:** Test something the mock doesn't hand you for free. Test that `get_user`
raises `UserNotFoundError` when Supabase returns empty data. Test that it strips
sensitive fields. Test that it handles connection errors.

## Testing the Mock, Not the Code

**What it looks like:**
```python
def test_create_embedding(mock_openai):
    await create_embedding("hello world")
    mock_openai.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="hello world"
    )
```

**Why it's weak:** This tests that you called the API with specific arguments. It
doesn't test what happens with the response, what happens on error, or whether
the embedding is stored correctly.

**Fix:** Assert on outcomes, not on calls. What does `create_embedding` return?
What happens when OpenAI returns an error? What if the response shape is unexpected?

## The Happy Path Only Endpoint Test

**What it looks like:**
```python
async def test_create_item(client):
    response = await client.post("/items", json={"name": "Test"})
    assert response.status_code == 200
```

**What's missing:**
- What happens with an empty name? (422?)
- What about a duplicate name? (409?)
- What if the user isn't authenticated? (401?)
- What if the user doesn't have permission? (403?)
- What if the request body is completely wrong? (422?)
- What if Supabase is down? (500 or graceful error?)

**Fix:** For every endpoint, test at minimum: happy path, validation failure,
auth failure, and one error case.

## Coverage Theater via Parametrize

**What it looks like:**
```python
@pytest.mark.parametrize("name", ["Alice", "Bob", "Charlie", "Diana", "Eve"])
def test_greet_user(name):
    assert greet(name) == f"Hello, {name}!"
```

**Why it's theater:** Five test cases exercising the exact same code path.
Coverage goes up. Confidence doesn't.

**When parametrize IS valuable:**
```python
@pytest.mark.parametrize("input,expected_error", [
    ("", "Name required"),           # empty string
    ("a" * 256, "Name too long"),    # boundary
    ("   ", "Name required"),        # whitespace only
    ("Alice", None),                 # valid
])
def test_validate_name(input, expected_error):
    ...
```
Each case exercises a different code path or boundary condition.

## The Snapshot Trap (Frontend)

**What it looks like:**
```typescript
test('renders correctly', () => {
  const { container } = render(UserProfile, { props: { user: mockUser } });
  expect(container).toMatchSnapshot();
});
```

**Why it fails in practice:** Snapshot diffs are noisy. They break on any markup
change. Developers update them reflexively without reading them. They test
structure, not behavior.

**Fix:** Test what matters to the user:
```typescript
test('displays user name and email', () => {
  render(UserProfile, { props: { user: { name: 'Alice', email: 'a@b.com' } } });
  expect(screen.getByText('Alice')).toBeInTheDocument();
  expect(screen.getByText('a@b.com')).toBeInTheDocument();
});
```

## The Test-Only Production Code

**What it looks like:**
```python
class UserService:
    def get_user(self, id):
        ...

    def _test_get_last_query(self):  # Added for testing
        return self._last_query
```

**Why it's harmful:** Production code should not contain test infrastructure.
It couples tests to internals and makes refactoring harder.

**Fix:** If you need to inspect internals, your design needs to change. Use
dependency injection to make the dependency observable from outside.

## The Invisible Integration Gap

**What it looks like:** Full unit test coverage, but the app breaks in production
because:
- The Supabase RLS policy blocks the query the code makes
- The OpenAI response format changed slightly
- The pgvector index isn't used because the query isn't structured right
- The auth token isn't passed through a middleware chain

**Fix:** You don't need to integration-test everything, but for critical paths
(auth flow, main data queries, embedding pipeline), have at least one test that
exercises the real code path with only the external service mocked at the HTTP boundary.

## Quick Smell Test

For any test file, ask:

1. **Remove all mocks mentally.** Does the test still make logical sense?
2. **Read only the assertions.** Do they describe behavior a user cares about?
3. **Imagine the implementation is completely wrong but returns the right shape.**
   Would these tests catch it?
4. **Count the assertions per test.** Zero or one trivial assertion = weak test.

If any answer is "no," the tests need work.
