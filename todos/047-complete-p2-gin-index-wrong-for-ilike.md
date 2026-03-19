---
status: complete
priority: p2
issue_id: "047"
tags: [code-review, performance, database, migrations, medications, pr-2]
dependencies: [040]
---

# GIN tsvector index on `medications_reference` doesn't serve ILIKE queries

## Problem Statement

The migration creates a GIN index using `to_tsvector` for medication reference search. But the `search_reference` method uses `ILIKE '%term%'` — a GIN tsvector index cannot serve ILIKE queries. The index is non-functional for its stated purpose, adds write overhead, and the planner falls back to a sequential scan on every search.

## Findings

- `backend/app/migrations/add_mht_medication_tracking.sql` lines 75–77
- Index: `CREATE INDEX ... USING gin(to_tsvector('english', coalesce(brand_name,'') || ' ' || generic_name))`
- `search_reference` uses: `.or_("brand_name.ilike.%term%,generic_name.ilike.%term%")`
- GIN tsvector → for `to_tsquery` full-text search. Cannot serve `ILIKE`.
- For substring ILIKE matching, the correct index is `pg_trgm` GIN: `USING gin(brand_name gin_trgm_ops, ...)`
- With only ~20 seed rows the performance impact is negligible now, but the index is doing nothing
- Identified by performance-oracle

## Proposed Solutions

### Option 1: Replace with `pg_trgm` GIN index (Recommended)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_medications_reference_search
    ON medications_reference
    USING gin((brand_name || ' ' || coalesce(generic_name, '')) gin_trgm_ops);
```

This serves ILIKE substring queries directly.

**Pros:** Index actually used, future-proof for larger reference tables
**Effort:** Small — migration update
**Risk:** Requires `pg_trgm` extension (available in Supabase by default)

### Option 2: Switch query to full-text search

Change `search_reference` to use `to_tsquery` with the existing `tsvector` index.

**Cons:** Changes search semantics — "estradiol" finds "estradiol patch" but "estr" does not (full-word only)
**Effort:** Medium

## Recommended Action

Option 1 — keep ILIKE semantics (users type partial names), just use the right index type.

## Technical Details

**Affected files:**
- `backend/app/migrations/add_mht_medication_tracking.sql` lines 75–77 (update index)

## Acceptance Criteria

- [ ] `pg_trgm` extension is enabled in the migration
- [ ] `idx_medications_reference_search` uses `gin_trgm_ops`
- [ ] Migration runs cleanly

## Work Log

- 2026-03-18: Identified by performance-oracle in PR #2 code review
- 2026-03-18: Approved during triage — status: pending → ready
