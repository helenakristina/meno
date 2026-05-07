---
name: testing-discipline
description: >
  Compound Engineering workflow hooks for TDD integration. Use when /ce:plan,
  /ce:work, /ce:review, or /ce:compound is invoked. Defines what each CE command
  activates for testing discipline across this project.
---

# Testing Discipline — CE Workflow Hooks

The full testing rules are in `.claude/rules/tdd-core.md` (always loaded) and
`.claude/rules/tests/backend.md` / `.claude/rules/tests/frontend.md` (path-scoped).
This skill defines what each CE command activates on top of those standing rules.

## /ce:plan

Before writing any code, state explicitly:

1. **Testing approach:** TDD (new code) or characterize-then-change (existing code) — and why
2. **What the first failing test will assert** — not "I'll write tests for X" but the
   specific behavior the first test will verify
3. **What external dependencies need mocking** and at which boundary

This step is non-negotiable. A plan without a test strategy is incomplete.

## /ce:work

**TDD is active.** The rules from `tdd-core.md` apply with no exceptions:

- No implementation code without a failing test first
- Every test gets a `# CATCHES:` comment before the session ends
- State mutation notes in your response for each test batch written
- If you catch yourself implementing before the test: stop, delete, write the test,
  watch it fail, reimplement

Call out explicitly when you're switching from RED to GREEN to REFACTOR.

## /ce:review

Load the `ce-review` skill. That skill owns the review procedure and checklist.

Surface all findings — critical, warnings, and test gaps. Silence is not a pass.

## /ce:compound

After the session, document anything new that emerged:

- New test fixtures or helpers added to `tests/fixtures/`
- New mock patterns that should be reused
- Any testing decisions made (why a certain layer was mocked at a specific boundary)
- Patterns that should be added to `tests/backend.md` or `tests/frontend.md` rules

This keeps the next session from rediscovering the same ground.
