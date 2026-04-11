---
name: Database Index Duplication on appointment_prep_metadata
status: complete
priority: p1
issue_id: 002
tags: [code-review, performance, database, blocking]
dependencies: []
---

## Problem Statement

The migration in `backend/app/migrations/add_appointment_prep_metadata_index.sql` creates a **duplicate index** that already exists in the database schema.

**New index (from PR):**

```sql
CREATE INDEX idx_appointment_prep_metadata_user_generated
ON appointment_prep_metadata(user_id, generated_at DESC);
```

**Existing index (already in schema):**

```sql
idx_appointment_prep_metadata_user_id (user_id, generated_at DESC)
```

Both indexes:

- Have identical column composition: `(user_id, generated_at DESC)`
- Serve the same query pattern in `get_user_prep_history()`
- Will both be maintained on every INSERT/UPDATE/DELETE

## Impact

**Performance degradation:**

- Every INSERT/UPDATE/DELETE maintains TWO indexes instead of one (~2x index write overhead)
- At 1M rows: ~5-10 MB disk space wasted
- INSERT latency increases by 5-10%
- Database maintenance burden doubles

## Findings

**From:** performance-oracle

**Severity:** CRITICAL (blocks merge)

**Location:** `backend/app/migrations/add_appointment_prep_metadata_index.sql`

**Query pattern that uses index:**

```python
# Line 702-707: Count query
count_response = await self.client.table("appointment_prep_metadata")
    .select("id", count="exact")
    .eq("user_id", user_id)
    .execute()

# Line 711-717: Paginated fetch
result = await self.client.table("appointment_prep_metadata")
    .select(...)
    .eq("user_id", user_id)
    .order("generated_at", desc=True)
    .range(offset, offset + limit)
    .execute()
```

Both queries filter on `user_id` and sort by `generated_at DESC` — exactly the columns in the existing index.

## Proposed Solutions

### Option A: Drop Pre-Existing Index (Recommended)

**Effort:** Small  
**Risk:** Low

Create a migration that drops the redundant index:

```sql
-- Keep only the newly named index
DROP INDEX IF EXISTS idx_appointment_prep_metadata_user_id;
```

Then keep the new index with better naming convention.

### Option B: Remove New Index from Migration

**Effort:** Minimal  
**Risk:** Low

Delete the migration file entirely and rely on existing index (if pre-existing is well-named and maintained).

### Option C: Keep Both (Not Recommended)

**Risk:** High — database bloat, performance degradation

## Recommended Action

Implement Option A: Drop the pre-existing index and keep the new one with improved naming (`idx_appointment_prep_metadata_user_generated`).

The new name is more explicit about the column ordering direction, which improves maintainability.

## Technical Details

**Affected files:**

- `backend/app/migrations/add_appointment_prep_metadata_index.sql`
- Possibly: `db/schema.rb` or Supabase schema state (not in PR scope)

## Acceptance Criteria

- [ ] One of the duplicate indexes is removed
- [ ] Migration verified to not create duplicate indexes
- [ ] Query execution time at 1000+ records per user is improved
- [ ] No new indexes created that duplicate existing ones
- [ ] Migration tests pass (if applicable)

## Work Log

| Date       | Action                                 | Result  |
| ---------- | -------------------------------------- | ------- |
| 2026-04-02 | Created from performance-oracle review | Pending |
