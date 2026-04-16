---
status: complete
priority: p1
issue_id: "125"
tags: [code-review, security, prompt-injection, rag]
---

# RAG chunk fields not sanitized before system prompt injection

## Problem Statement

`backend/app/utils/context_builder.py` lines 50–53 embed RAG chunk `title`, `source_url`, and `content` directly into the LLM system prompt with no call to `sanitize_prompt_input`:

```python
url = chunk.get("source_url", "")
title = chunk.get("title", "").strip()
content = chunk.get("content", "").strip()
source_lines.append(f"(Source {i}) {title}\nURL: {url}\nContent: {content}")
```

`.strip()` does not remove embedded newlines, role markers (`SYSTEM:`, `USER:`), or XML tags. If the ingest pipeline ever processes a compromised document (bad PubMed record, malicious Wikipedia edit, corrupted import), attacker-controlled content lands verbatim in the system prompt.

`symptom_summary` (also DB-sourced) is correctly sanitized on line 116. The omission on chunk fields is inconsistent. This is a known pattern — see `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md`.

There are no tests for this attack surface. `test_context_builder.py` tests injection via medication fields but not via chunk `title`, `content`, or `source_url`.

## Proposed Solution

Apply `sanitize_prompt_input` to `title` and `content` with appropriate `max_length`:

```python
url = chunk.get("source_url", "")[:500]  # length cap; URLs can't contain injection
title = sanitize_prompt_input(chunk.get("title", ""), max_length=200)
content = sanitize_prompt_input(chunk.get("content", ""), max_length=2000)
source_lines.append(f"(Source {i}) {title}\nURL: {url}\nContent: {content}")
```

Add tests in `test_context_builder.py` for `title` and `content` containing `\nSYSTEM: override`.

**Effort:** Small  
**Risk:** None — `sanitize_prompt_input` is already used on all other user-sourced fields in the same function

## Acceptance Criteria

- [ ] `title` and `content` from RAG chunks pass through `sanitize_prompt_input` before being formatted into the prompt
- [ ] `source_url` has a length cap
- [ ] Tests verify that injection markers in chunk `title` and `content` are stripped

## Work Log

- 2026-04-15: Identified by PR #25 code review (security-sentinel + learnings-researcher). Learnings doc `docs/solutions/security-issues/prompt-injection-sanitization-llm-prompts.md` names this exact pattern.
