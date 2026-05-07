# TDD Core

Every test in this project must be able to fail for a meaningful reason.
If a test can pass with a wrong implementation, it is not a test — it is theater.

## The CATCHES Requirement

Every test must have a comment stating what realistic bug it would catch:

```python
# CATCHES: [description of a specific, realistic bug this test would detect]
```

If you cannot fill in the blank concretely, do not write the test. This requirement
applies to every test in every language — Python, TypeScript, Svelte.

## New Code: TDD Cycle

1. **RED** — Write one test for one behavior. Run it. Watch it fail.
2. **Verify RED** — Confirm it fails because the feature is missing, not a typo.
3. **GREEN** — Write the minimum code to pass. Nothing more.
4. **Verify GREEN** — Run the test. Run the suite. Everything green.
5. **REFACTOR** — Clean up. Tests stay green. No new behavior.
6. **Repeat** — Next behavior, next test.

**The iron law:** No implementation code without a failing test first.
Wrote implementation before the test? Delete it. Write the test. Watch it fail. Reimplement.

## Existing Code: Characterize Before Changing

1. Write a test capturing current behavior. Run it — it must pass.
2. Write a test for the desired new behavior. Run it — it must fail.
3. Implement the change.
4. Both tests pass (unless you are intentionally changing the characterized behavior).

## Mutation Notes

When writing tests, state in your response which 2-3 specific bugs these tests
would catch. Example: "These tests would catch: ORDER BY becoming ASC; top_k
parameter ignored; empty result raising IndexError instead of returning []."

If you cannot list concrete mutations, the tests need to be stronger.

## The Self-Confirmation Problem

When the same session writes code and tests, tests tend to verify what was built
rather than what was required. After writing tests, apply this check:

1. Could this test pass with a wrong implementation?
2. If I introduced [specific bug], would this test catch it?
3. Does this test assert on behavior or on implementation details?

If #1 is yes, the test is too weak. If #2 is no, something is missing.
If #3 is implementation details, rewrite it.

## Blocked on TDD?

If a dependency does not exist yet, define its interface (ABC or stub) first,
write the test against that interface with a mock, then implement the real thing.
"The dependency doesn't exist yet" is never a reason to skip the failing test step.
