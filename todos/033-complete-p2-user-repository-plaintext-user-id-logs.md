---
status: pending
priority: p2
issue_id: "033"
tags: [code-review, pii, logging, backend, security]
dependencies: []
---

# `user_repository.py` has ~11 plaintext `user_id` log statements

## Problem Statement

Multiple pre-existing methods in `user_repository.py` log raw `user_id` in plaintext, violating the PII-safe logging policy (CLAUDE.md: "never log user IDs without hash_user_id()"). This branch modified `user_repository.py` and added new methods using `hash_user_id()` correctly, making the inconsistency visible.

## Findings

Plaintext `user_id` at these lines (approx): 57-58, 65, 77, 104-105, 114, 140-141, 150, 182-183, 220-221, 331-332, 341.

- `hash_user_id` import already present (added by this branch)
- New methods `get_settings`/`update_settings` use it correctly
- Old methods do not

## Proposed Solution

Replace `user_id` with `hash_user_id(user_id)` in all logger calls throughout `user_repository.py`. The import is already there.

## Acceptance Criteria
- [ ] All log statements in `user_repository.py` use `hash_user_id(user_id)`
- [ ] No raw UUID visible in any log line
