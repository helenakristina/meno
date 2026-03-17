---
status: pending
priority: p3
issue_id: "038"
tags: [code-review, yagni, backend]
dependencies: []
---

# `PeriodLogListResponse.total` is YAGNI — always equals `len(logs)`

## Problem Statement

`PeriodLogListResponse` has a `total: int` field set to `len(logs)`. No pagination exists. The frontend doesn't use `total` separately from `logs.length`. This is pre-built infrastructure for a feature that doesn't exist.

## Proposed Solution

Remove `total` from `PeriodLogListResponse` and from `get_logs` in the service. If pagination is added later, add `total` back then with real semantics.

Note: This is a schema change — only remove if no external consumer depends on `total`. Safe to remove if the frontend is the only consumer.

## Acceptance Criteria
- [ ] `PeriodLogListResponse` has only `logs: list[PeriodLogResponse]`
- [ ] Frontend updated to use `logs.length` directly
- [ ] Tests updated
