---
status: pending
priority: p3
issue_id: "037"
tags: [code-review, simplicity, backend]
dependencies: []
---

# `check_postmenopausal_bleeding_alert` is a one-liner — inline it

## Problem Statement

`PeriodService.check_postmenopausal_bleeding_alert` is a public method with a 9-line docstring that wraps `journey_stage == "post-menopause"`. It adds no logic, no reuse, no safety. The method exists as a pure passthrough boolean expression.

## Proposed Solution

In `create_log`, replace:
```python
bleeding_alert = self.check_postmenopausal_bleeding_alert(journey_stage)
```
with:
```python
bleeding_alert = journey_stage == "post-menopause"
```

Delete the method entirely. Remove from tests (or update to test `create_log` outcome).

## Acceptance Criteria
- [ ] Method removed, expression inlined
- [ ] Tests updated to verify `bleeding_alert` via `create_log` result
