-- Migration: Fix PMC ID unique constraint
-- Created: 2026-02-28
-- Purpose: Remove UNIQUE constraint from pmc_id to allow multiple chunks per article

BEGIN;

-- Drop the UNIQUE constraint if it exists
-- (Some databases may have auto-generated constraint names)
ALTER TABLE rag_documents DROP CONSTRAINT IF EXISTS rag_documents_pmc_id_key;

-- Ensure the index still exists for fast lookups (non-unique)
DROP INDEX IF EXISTS idx_rag_documents_pmc_id;
CREATE INDEX idx_rag_documents_pmc_id ON rag_documents(pmc_id) WHERE pmc_id IS NOT NULL;

COMMIT;
