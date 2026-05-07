---
paths:
  - backend/app/utils/**/*.py
---

# Utils Rules

Utils are pure functions. No side effects, no database access, no API calls,
no `self._repo`, no `self._llm`, no `AsyncClient`.

## The Mock Test

If you could test this function with no mocks — just input → output — it belongs
in utils. If it needs a mock, it belongs in a service or repository.

## Belongs Here

- Date calculations and formatting
- Stat formatting (averages, streaks, frequency counts)
- Text sanitization and truncation
- Token counting
- PII hashing (`hash_user_id`, `safe_len`, `safe_keys`, `safe_summary`)
- Unit conversions

## Does Not Belong Here

Anything that calls a repository, an LLM, or touches `AsyncClient`.

## Testing Utils

No mocks needed — just call the function with inputs and assert on outputs.

```python
# CATCHES: Token counter returns 0 for empty string instead of raising
def test_count_tokens_returns_zero_for_empty_string():
    assert count_tokens("") == 0

# CATCHES: PII hash is deterministic (same input → same output) so logs
#          can be correlated without exposing the raw user ID
def test_hash_user_id_is_deterministic():
    assert hash_user_id("user-abc") == hash_user_id("user-abc")

# CATCHES: Hash leaks the original user ID by being reversible or too short
def test_hash_user_id_does_not_expose_original():
    result = hash_user_id("user-abc-123")
    assert "user-abc-123" not in result
    assert len(result) >= 16
```
