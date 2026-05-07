---
name: ce-review
description: >
  Code review procedure for the /ce:review command. Audits tests for CATCHES
  comments, mutation coverage, self-confirmation bias, and architectural
  violations. Use at the end of a /ce:work session before merging.
---

# CE Review

Run this at the end of every `/ce:work` session. This is not a rubber stamp —
surface findings even if minor. Silence in review is not a pass.

## 1. Test Quality Audit

For every new or modified test:

**CATCHES comment check:**

- Does every test have a `# CATCHES:` comment?
- Is the CATCHES description concrete and specific? ("user_id filter ignored"
  is specific; "validation works" is not)
- If any test is missing a CATCHES comment, flag it

**Mutation coverage check:**
Mentally introduce each of these bugs and ask: would the tests catch it?

- Off-by-one in a loop or slice
- Swapped conditional (`>` instead of `>=`, `==` instead of `is`)
- Missing null/empty check
- Wrong variable in a return statement
- `ORDER BY ASC` instead of `DESC`
- Filter condition removed entirely
- Return `[]` instead of raising, or raise instead of returning `[]`

If a mutation would NOT be caught, the test is confirming implementation,
not guarding behavior. Flag it and suggest a stronger assertion.

**Self-confirmation check:**
When the same session wrote both code and tests, apply extra scrutiny:

1. Could any test pass with a wrong implementation?
2. Does any test assert on internal structure rather than observable behavior?
3. Are there realistic bugs in the implementation that zero tests would catch?

## 2. Architectural Violations

**Backend:**

- [ ] Routes contain business logic (anything beyond call service + return)
- [ ] Routes call repositories directly
- [ ] Services instantiate their own dependencies in `__init__`
- [ ] Services raise `HTTPException`
- [ ] Repositories return raw dicts instead of Pydantic models
- [ ] Missing `user_id` filter on any user-data repository query
- [ ] Concrete classes in `dependencies.py` missing (wired elsewhere)
- [ ] `@retry_transient` missing on external API calls

**Frontend:**

- [ ] Svelte 4 syntax used (`export let`, `on:click`, `<slot />`)
- [ ] `apiClient` imported in a server file
- [ ] `locals.token` missing in a server action
- [ ] `$effect` used where `onMount` or `$derived` is correct
- [ ] Form input bound to local state instead of `$formData`
- [ ] `{@html}` used without `DOMPurify.sanitize()`
- [ ] Auth check missing in server action

**PII / Medical:**

- [ ] Any logging of user IDs, content, or health data without helpers
- [ ] Any code path that could generate diagnosis or treatment advice
- [ ] LLM calls that include raw symptom logs (not calculated patterns)

## 3. Summary Format

Report findings in this structure:

```
FINDINGS: [n issues found / clean]

Critical (must fix before merge):
- [file:line] [description]

Warnings (should fix):
- [file:line] [description]

Test gaps (mutations not caught):
- [test name]: would not catch [specific bug]

CATCHES audit: [n/total tests have CATCHES comments]
```

If the session is clean, say so explicitly with "No findings."

Reference: see `anti-patterns.md` in this directory for detailed examples
of each failure mode.
