---
name: Database Index for appointment_prep_metadata
status: complete
priority: p2
tags: [code-review, performance, database]
dependencies: []
---

## Problem Statement

Missing database index on `appointment_prep_metadata` table causes O(n) table scans on history queries.

## Findings

**From:** performance-oracle

**Location:** `backend/app/repositories/appointment_repository.py` lines 698-715 (`get_user_prep_history`)

**Query pattern:**

```python
count_response = (
    await self.client.table("appointment_prep_metadata")
    .select("id", count="exact")
    .eq("user_id", user_id)
    .execute()
)
# ... followed by range query with ordering
```

**Impact:** At 1000+ records per user, queries slow to 50-100ms.

## Proposed Solutions

### Option A: Add Composite Index (Recommended)

**Effort:** Small
**Risk:** Low

Add migration:

```sql
CREATE INDEX IF NOT EXISTS idx_appointment_prep_metadata_user_generated
ON appointment_prep_metadata(user_id, generated_at DESC);
```

This supports both the count query and the paginated fetch with ordering.

### Option B: Accept Current Performance

**Risk:** Queries will degrade as user history grows.

## Recommended Action

Add the composite index migration.

## Technical Details

**New migration file needed:** Add to existing migrations

**Affected queries:**

- `get_user_prep_history()` count query
- `get_user_prep_history()` paginated fetch

## Acceptance Criteria

- [ ] Migration file created with composite index
- [ ] Index creation tested in local environment
- [ ] Query execution time verified improved via EXPLAIN ANALYZE

## Work Log

| Date       | Action                         | Result  |
| ---------- | ------------------------------ | ------- |
| 2026-03-31 | Created from performance audit | Pending |
