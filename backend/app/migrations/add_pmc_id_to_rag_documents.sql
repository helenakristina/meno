-- Migration: Add PMC ID column to rag_documents for PubMed deduplication
-- Created: 2026-02-27
-- Purpose: Enable upsert on PMC ID so PubMed scraper can re-run without duplicates

BEGIN;

-- Add pmc_id column (nullable initially to handle existing wiki data)
-- Note: NOT UNIQUE — multiple chunks can have the same pmc_id (one article, many chunks)
-- We delete-and-insert for re-runs rather than relying on UNIQUE constraints
ALTER TABLE rag_documents ADD COLUMN pmc_id TEXT NULL;

-- Add index for faster lookups
CREATE INDEX idx_rag_documents_pmc_id ON rag_documents(pmc_id) WHERE pmc_id IS NOT NULL;

-- Add comment explaining the column
COMMENT ON COLUMN rag_documents.pmc_id IS 'PubMed Central article ID (PMC7123456). Used for deduplication and upserts.';

COMMIT;
