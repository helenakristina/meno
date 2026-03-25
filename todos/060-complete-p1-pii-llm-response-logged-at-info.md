---
status: complete
priority: p1
issue_id: "060"
tags: [code-review, security, pii, logging, ask-meno]
dependencies: []
---

# PII: LLM response content logged at INFO level in production

## Problem Statement

`ask_meno.py` logs the raw LLM response content and rendered text at INFO level. These strings are derived from and directly reflect the user's health question, symptom summary, age, journey stage, cycle data, and medication context. This is PHI (Protected Health Information) in logs, violating CLAUDE.md's explicit rule: "Health app logs must NEVER contain personal or medical data."

Both log lines fire on every successful Ask Meno request and will appear in Railway logs, any future log aggregator, and any Sentry integration.

## Findings

- `backend/app/services/ask_meno.py:276–280` — `json.dumps(raw_response)[:2000]` — logs full LLM JSON output
- `backend/app/services/ask_meno.py:288–292` — `response_text[:500]` — logs rendered assistant message
- Both at `logger.info`, not `logger.debug` — no conditional guard
- Confirmed by: python-reviewer, performance-oracle, security-sentinel, agent-native-reviewer

## Proposed Solutions

### Option 1: Replace with structural metadata (Recommended)

**Approach:** Log only counts, flags, and shapes. Never log LLM output content.

```python
# Instead of logging raw_response content:
logger.info(
    "Structured LLM response for user=%s: sections=%d insufficient=%s disclaimer=%s",
    hash_user_id(user_id),
    len(raw_response.get("sections", [])),
    raw_response.get("insufficient_sources"),
    bool(raw_response.get("disclaimer")),
)

# Instead of logging response_text content:
logger.info(
    "Rendered response for user=%s: len=%d citations=%d",
    hash_user_id(user_id),
    safe_len(response_text),
    len(citations),
)
```

**Pros:** Zero PHI exposure, still operationally useful, consistent with existing PII-safe logging pattern.
**Cons:** None.
**Effort:** Small.
**Risk:** None.

### Option 2: Move to DEBUG level

**Approach:** Change `logger.info` to `logger.debug` so content only appears in dev.

**Pros:** Minimal change.
**Cons:** Doesn't solve the problem if DEBUG logging is ever enabled in production; still violates the explicit policy.
**Effort:** Trivial.
**Risk:** False sense of security — doesn't eliminate the log, just changes the level.

## Recommended Action

Option 1. Delete content-bearing logs; replace with structural metadata.

## Technical Details

- **Affected files:** `backend/app/services/ask_meno.py`
- **Lines:** 276–292

## Acceptance Criteria

- [ ] Lines 276–280 replaced with structural metadata log (sections count, insufficient_sources flag, disclaimer present)
- [ ] Lines 288–292 replaced with `safe_len(response_text)` and citation count
- [ ] No LLM-generated text appears in any log statement in `ask_meno.py`
- [ ] Tests pass

## Work Log

- 2026-03-23: Found by python-reviewer, security-sentinel, performance-oracle, agent-native-reviewer in code review of PR #4
- 2026-03-24: Approved during triage session. Status changed pending → ready.
