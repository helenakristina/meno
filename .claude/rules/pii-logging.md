# PII-Safe Logging

Meno handles sensitive health data. Log files must never contain personal or
medical information. This applies to every file in this project.

## Never Log

- User IDs in plain text
- Symptom descriptions or severity values
- User-generated text of any kind
- Health information, notes, or patterns
- Dates of birth or demographic details
- Prompt content or LLM responses (log size only)
- Any content that could identify or profile a user

## Always Use These Helpers

```python
from app.utils.logging import hash_user_id, safe_len, safe_keys, safe_summary
```

| You have            | Use                                              |
| ------------------- | ------------------------------------------------ |
| `user_id`           | `hash_user_id(user_id)`                          |
| Content string      | `safe_len(content)` — logs character count only  |
| Dict with user data | `safe_keys(d)` — logs key names only, not values |
| Operation result    | `safe_summary(operation, status)`                |

## Examples

```python
# NO
logger.info("User %s asked: %s", user_id, prompt)
logger.debug("Symptoms: %s", symptom_data)
logger.error("Failed for user %s with data %s", user_id, payload)

# YES
logger.info("Generating completion for user: %s", hash_user_id(user_id))
logger.debug("LLM request: system=%d chars, user=%d chars", safe_len(system), safe_len(user))
logger.error("Failed to persist symptom log for user: %s", hash_user_id(user_id))
```

Full reference: `docs/dev/backend/LOGGING.md`
