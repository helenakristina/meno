# Safe Logging for Health Data

Meno is a health application. **Logs must NEVER contain personal or medical information.**

This document explains why, how to log safely, and utilities that make safe logging easy.

## Quick Reference

### ✅ Safe to Log

- Operation status ("success", "error", "timeout")
- Data sizes and types (`safe_len()`, `safe_type()`)
- Hashed user IDs (`hash_user_id()`)
- Execution time and performance metrics
- System errors and exception types
- HTTP status codes and response headers

### ❌ Never Log

- Symptom descriptions or medical data
- User-generated notes or free-text entries
- Prompts sent to LLM (may contain medical info)
- Response content from LLM
- Personal health information (age, DOB, medical history)
- User IDs in plaintext
- Full request/response bodies
- Email addresses
- Search queries
- Appointment notes or descriptions

## Why This Matters

### Legal Compliance

Logging PII in a health app violates:

- **HIPAA** (US health data privacy law)
  - Up to $1.5M per violation
  - Mandatory breach notification to users
  - Required forensic investigation
- **GDPR** (EU data protection regulation)
  - Up to €20 million fine
  - Data subject rights (right to be forgotten, etc.)
  - Mandatory data protection impact assessments
- **State Laws** (California CCPA, etc.)
  - Consumer right to data deletion
  - Right to know what data is collected
  - Right to opt out of sale

### Ethical Responsibility

Users entrust us with sensitive health information. They expect:
- Their data stays private
- Debug logs won't expose their conditions
- Logs can't be exploited if there's a breach

### Technical Reality

**Logs are not private.** They're often:
- Stored in centralized systems (Datadog, CloudWatch, etc.)
- Accessible to multiple team members and services
- Retained for weeks, months, or years
- Subject to subpoenas or regulatory requests
- Visible in staging/development environments
- Cached in monitoring dashboards
- Accessible in crash reports

**Treat all logs as potentially readable.**

## Examples

### Wrong (Dangerous)

```python
# ❌ Logs medical data
logger.debug("Processing symptom log: %s", data[:100])
# Output: "Processing symptom log: {'symptoms': ['hot_flashes', 'brain_fog'], 'severity': 8}"

# ❌ Logs prompt content (may contain medical info)
logger.info("LLM prompt: %s", prompt)
# Output: "LLM prompt: You are Meno AI. User reports: severe fatigue, sleep disruption 3x/week..."

# ❌ Logs user ID in plaintext
logger.debug("User: %s", user_id)
# Output: "User: 550e8400-e29b-41d4-a716-446655440000"

# ❌ Logs LLM response
logger.info("Response: %s", response[:200])
# Output: "Response: Your fatigue appears correlated with sleep disruption. Consider discussing..."
```

### Right (Safe)

```python
from app.utils.logging import safe_len, safe_summary, hash_user_id

# ✅ Logs only the size
logger.debug("Processing symptom log: %d bytes", safe_len(data))
# Output: "Processing symptom log: 127 bytes"

# ✅ Logs only the length and type
logger.debug("LLM call: %d input chars (type: %s)", safe_len(prompt), safe_type(prompt))
# Output: "LLM call: 342 input chars (type: str)"

# ✅ Logs hashed user ID
logger.debug("User: %s", hash_user_id(user_id))
# Output: "User: user_a3f2b1cd"

# ✅ Logs operation summary
logger.info(safe_summary("generate narrative", "success", duration_ms=234.5))
# Output: "generate narrative: success (234.5ms)"
```

## Safe Logging Utilities

All utilities are in `app.utils.logging`. Import what you need:

```python
from app.utils.logging import (
    hash_user_id,
    hash_appointment_id,
    safe_len,
    safe_type,
    safe_keys,
    safe_summary,
)
```

### hash_user_id(user_id: str) → str

Hash a user ID for safe logging. User IDs should never appear in plaintext.

**Returns:** Hashed ID like `"user_a3f2b1cd"` (prefix + first 8 chars of SHA-256)

**Example:**

```python
logger.info("Processing for user: %s", hash_user_id(user_id))
# Output: "Processing for user: user_a3f2b1cd"

# Same user → same hash (consistent per user)
logger.info("Cached result for: %s", hash_user_id(same_user_id))
# Output: "Cached result for: user_a3f2b1cd"
```

**Benefits:**
- Logs are consistent per user (good for grouping)
- Can't identify users from logs (safe)
- Can't reverse-engineer user IDs (hashing is one-way)

### hash_appointment_id(appointment_id: str) → str

Hash an appointment ID. Same as `hash_user_id()` but with `"appt_"` prefix.

**Example:**

```python
logger.info("Appointment: %s", hash_appointment_id(appt_id))
# Output: "Appointment: appt_c8d4e2f1"
```

### safe_len(data: Any) → int

Get length of data without logging the data itself. Useful for logging "processed 500 characters" without exposing content.

**Example:**

```python
logger.debug("Processing request: %d bytes", safe_len(request_body))
# Safe: Only logs the length, not the content

logger.debug("Response: %d chars", safe_len(response_text))
# Only logs size, not the medical narrative inside
```

### safe_type(data: Any) → str

Get type name of data for logging without revealing content.

**Example:**

```python
logger.debug("Received: %s", safe_type(response))
# Output: "Received: dict"

logger.debug("Data types: %s, %s", safe_type(logs), safe_type(symptoms))
# Output: "Data types: list, str"
```

### safe_keys(data: dict) → str

Get dict keys for logging without revealing values. Shows structure without exposing sensitive content.

**Example:**

```python
logger.debug("Response structure: %s", safe_keys(response))
# Output: "Response structure: id, created_at, user_id, content"

logger.debug("User data fields: %s", safe_keys(user))
# Output: "User data fields: id, email, age, journey_stage"
# (Shows structure but no values)
```

### safe_summary(operation: str, status: str, count: int = None, duration_ms: float = None) → str

Create a safe log message summarizing an operation. Useful for operation results without exposing data.

**Example:**

```python
logger.info(safe_summary("fetch logs", "success", count=47, duration_ms=123.5))
# Output: "fetch logs: success (47 items, 123.5ms)"

logger.info(safe_summary("generate narrative", "success", duration_ms=234.5))
# Output: "generate narrative: success (234.5ms)"

logger.warning(safe_summary("LLM call", "error"))
# Output: "LLM call: error"
```

## Patterns by Context

### Repositories (Database Access)

```python
from app.utils.logging import safe_len, hash_user_id, safe_summary
import logging

logger = logging.getLogger(__name__)

class SymptomRepository:
    async def get_logs(self, user_id: str, days: int) -> list[SymptomLog]:
        """Fetch symptom logs for a user."""
        logger.debug("Fetching logs for: %s (past %d days)", hash_user_id(user_id), days)

        try:
            response = await self.client.table("symptom_logs").select("*").execute()
            logs = [SymptomLog(**item) for item in response.data]

            logger.debug("Fetched %d logs (%d bytes)", len(logs), safe_len(response.data))
            return logs

        except Exception as e:
            logger.error("Failed to fetch logs: %s", type(e).__name__)
            raise DatabaseError(f"Failed to fetch logs: {e}") from e
```

**Key points:**
- Log the hashed user ID, not the plaintext ID
- Log the count, not the content
- Log the operation and status
- Never log the actual symptom data

### Services (Business Logic)

```python
from app.utils.logging import safe_len, safe_summary, hash_user_id
import logging

logger = logging.getLogger(__name__)

class AppointmentPrepService:
    async def generate_narrative(self, user_id: str, context: AppointmentContext) -> str:
        """Generate a narrative for appointment prep."""
        logger.info("Generating narrative for: %s", hash_user_id(user_id))

        # Calculate stats (never log the raw logs)
        stats = self._calculate_stats(context)
        logger.debug("Stats: %d symptom pairs analyzed", len(stats))

        # Call LLM (never log the prompt or response)
        logger.debug("Calling LLM: %d input chars", safe_len(self._build_prompt(stats)))

        narrative = await self.llm_provider.chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_prompt(stats),
        )

        logger.info(safe_summary("generate narrative", "success", duration_ms=234.5))
        return narrative
```

**Key points:**
- Log the operation name and hashed user ID
- Log counts and metadata, not content
- Log operation duration but not prompt/response content
- Use `safe_summary()` for clean operation logging

### LLM Providers

```python
from app.utils.logging import safe_len
import logging

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    async def chat_completion(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Call OpenAI API."""
        logger.debug(
            "LLM request: %d system chars, %d user chars",
            safe_len(system_prompt),
            safe_len(user_prompt),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **kwargs,
            )

            content = response.choices[0].message.content or ""
            logger.debug("LLM response: %d chars", safe_len(content))
            return content.strip()

        except TimeoutError:
            logger.error("LLM request timed out")
            raise
        except Exception as e:
            logger.error("LLM error: %s", type(e).__name__)
            raise
```

**Key points:**
- Log input/output sizes, not content
- Never log prompts or responses
- Log error type, not error message (which might contain input data)

### Routes (API Endpoints)

```python
from app.utils.logging import hash_user_id, safe_summary
import logging

logger = logging.getLogger(__name__)

@router.post("/api/symptoms/logs")
async def create_log(
    payload: CreateSymptomLogRequest,
    user_id: CurrentUser,
    repo: SymptomRepository = Depends(get_repo),
) -> CreateSymptomLogResponse:
    """Create a symptom log."""
    logger.info("Creating log for user: %s", hash_user_id(user_id))

    try:
        # Don't log the request payload (it contains medical data)
        log_id = await repo.create(user_id, payload)

        logger.info("Log created: %s", log_id)
        return CreateSymptomLogResponse(id=log_id)

    except ValidationError as e:
        logger.warning("Validation error for user: %s", hash_user_id(user_id))
        raise HTTPException(status_code=400, detail=str(e))
```

**Key points:**
- Log the user (hashed) and operation
- Never log the request payload
- Log success with the resource ID
- Log validation errors by type, not content

## Testing Logging

Always verify that logs don't contain PII. Use pytest's `caplog` fixture:

```python
import pytest

@pytest.mark.asyncio
async def test_no_pii_in_logs(caplog):
    """Verify logs don't contain sensitive health data."""
    # Run some operation
    result = await service.do_something(user_id, medical_data)

    # Check that plaintext IDs aren't logged
    assert user_id not in caplog.text

    # Check that medical terms aren't logged
    assert "symptom" not in caplog.text.lower()
    assert "fatigue" not in caplog.text.lower()

    # Check that prompts aren't logged
    assert medical_data not in caplog.text

    # But hashed values SHOULD be present
    from app.utils.logging import hash_user_id
    assert hash_user_id(user_id) in caplog.text
```

### Automated Check

Add a test utility to catch common PII logging mistakes:

```python
# tests/utils/test_logging_safety.py

def test_repository_logs_no_user_ids(caplog):
    """Catch if raw user IDs are logged."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    # ... run repository method ...
    # Fail if the plaintext ID appears in logs
    assert user_id not in caplog.text
```

## Checklist for Code Review

When reviewing backend code, check:

- [ ] No plaintext user IDs in logs (use `hash_user_id()`)
- [ ] No medical data logged (symptoms, notes, etc.)
- [ ] No prompt/response content logged (use `safe_len()`)
- [ ] No request/response bodies logged
- [ ] Log messages use `safe_summary()` for operations
- [ ] Test coverage includes PII safety checks
- [ ] All LLM calls only log metadata (not prompts/responses)
- [ ] Database errors logged by type, not content

## Quick Grep Check

Find potential PII logging in code:

```bash
# Find logger calls that might expose data
grep -r "logger\.\(debug\|info\|warning\)" backend/app --include="*.py" | grep -E '"%s"|\.format\(|f"'

# Check for common mistakes
grep -r "logger.debug.*data\|logger.info.*user_id\|logger.debug.*prompt" backend/app
```

## Reference: All Utilities

| Function | Purpose | Returns |
|----------|---------|---------|
| `hash_user_id(uid)` | Hash user ID for safe logging | `"user_a3f2b1cd"` |
| `hash_appointment_id(aid)` | Hash appointment ID | `"appt_c8d4e2f1"` |
| `safe_len(data)` | Get length without exposing content | `int` |
| `safe_type(data)` | Get type name | `"dict"`, `"list"`, etc. |
| `safe_keys(dict)` | Get dict keys | `"id, created_at, user_id"` |
| `safe_summary(op, status, count, duration)` | Create summary message | `"operation: status (count items, 123ms)"` |

All in `app.utils.logging`. Import and use freely.

## Resources

- **HIPAA:** https://www.hhs.gov/hipaa/
- **GDPR:** https://gdpr-info.eu/
- **California CCPA:** https://oag.ca.gov/privacy/ccpa
- **Secure Logging Best Practices:** https://owasp.org/www-community/attacks/Log_Injection
