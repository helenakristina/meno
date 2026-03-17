---
status: pending
priority: p3
issue_id: "036"
tags: [code-review, logging, backend]
dependencies: []
---

# Create/delete period logs produce 3 log lines each (route + service + repo)

## Problem Statement

Creating or deleting a period log fires `logger.info` in the repository, service, AND route handler — three log lines for one user action. Project convention (Routes = HTTP only) points to the service as the right log point.

## Proposed Solution

Remove `logger.info` from route handlers (`routes/period.py` lines 43, 108). Keep service-level logs. Remove repository-level success logs (keep error logs).

## Acceptance Criteria
- [ ] One log line per create/delete action (at service layer)
- [ ] Error/warning logs preserved at all layers
