"""End-to-end test for the RAG ingestion and retrieval pipeline.

Chunks a sample document, generates embeddings, stores them in Supabase,
then retrieves results for a test query and prints them for manual review.

Prerequisites:
  1. OPENAI_API_KEY set in backend/.env
  2. SUPABASE_URL and SUPABASE_SERVICE_KEY set in backend/.env
  3. rag_documents table exists in Supabase (pgvector enabled)
  4. match_rag_documents SQL function created in Supabase
     (see the SQL definition at the top of app/rag/retrieval.py)

Run from the backend directory:
    cd backend
    uv run python scripts/test_rag.py
"""
import asyncio
import logging
import sys
from pathlib import Path

# Ensure 'app.*' imports resolve when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.rag.ingest import chunk_document, generate_embeddings, store_chunks  # noqa: E402
from app.rag.retrieval import retrieve_relevant_chunks  # noqa: E402

# ---------------------------------------------------------------------------
# Sample document (hot flashes from Menopause Wiki)
# ---------------------------------------------------------------------------

SAMPLE_TEXT = """
Hot flashes are sudden feelings of warmth, usually most intense over the face,
neck and chest. They are caused by changes in hormone levels, particularly
declining estrogen. During a hot flash, blood vessels near the skin surface
widen to cool the body, causing redness and sweating. Episodes typically last
between 30 seconds and 10 minutes. Hot flashes are one of the most common
symptoms of perimenopause and menopause, affecting up to 75% of women.

The frequency and intensity of hot flashes vary widely between individuals.
Some women experience mild, occasional hot flashes while others have severe
episodes many times per day. Night sweats are hot flashes that occur during
sleep and can lead to significant sleep disruption.

Triggers for hot flashes can include caffeine, alcohol, spicy foods, stress,
and warm environments. Research suggests that the thermoregulatory zone — the
range of body temperatures the brain tolerates before triggering cooling
mechanisms — narrows significantly during menopause. This narrowing means even
small temperature increases can trigger a hot flash response.

Hormone therapy, particularly estrogen therapy, remains the most effective
treatment for hot flashes according to current evidence from The Menopause
Society and the British Menopause Society. Non-hormonal options including
certain antidepressants, gabapentin, and lifestyle modifications may also
reduce frequency and severity for women who cannot or prefer not to use
hormone therapy.
"""

SAMPLE_TITLE = "Hot Flashes: Causes, Symptoms and Management"
SAMPLE_URL = "https://menopausewiki.ca/symptoms/hot-flashes"
SAMPLE_QUERY = "What causes hot flashes?"

# Use smaller chunks for the test doc so we get multiple chunks to search over
TEST_CHUNK_SIZE = 80   # tokens (~320 chars)
TEST_OVERLAP = 15      # tokens (~60 chars)


async def main() -> None:
    print("\n=== RAG Pipeline Test ===\n")

    # ------------------------------------------------------------------
    # Step 1: Chunk
    # ------------------------------------------------------------------
    print("Step 1: Chunking document...")
    chunks = chunk_document(
        text=SAMPLE_TEXT,
        title=SAMPLE_TITLE,
        source_url=SAMPLE_URL,
        chunk_size=TEST_CHUNK_SIZE,
        overlap=TEST_OVERLAP,
        section_name="Vasomotor Symptoms",
    )
    print(f"  → {len(chunks)} chunks created\n")
    for i, c in enumerate(chunks):
        preview = c["content"][:90].replace("\n", " ")
        print(f"  Chunk {i} ({len(c['content'])} chars): {preview}...")

    # ------------------------------------------------------------------
    # Step 2: Generate embeddings
    # ------------------------------------------------------------------
    print(f"\nStep 2: Generating embeddings for {len(chunks)} chunks...")
    texts = [c["content"] for c in chunks]
    embeddings = await generate_embeddings(texts)
    print(f"  → {len(embeddings)} embeddings generated (dim={len(embeddings[0])})")

    # ------------------------------------------------------------------
    # Step 3: Store in Supabase
    # ------------------------------------------------------------------
    print("\nStep 3: Storing chunks in rag_documents table...")
    await store_chunks(chunks, embeddings, source_type="wiki")
    print("  → Stored successfully")

    # ------------------------------------------------------------------
    # Step 4: Retrieve
    # ------------------------------------------------------------------
    print(f"\nStep 4: Querying: '{SAMPLE_QUERY}'")
    results = await retrieve_relevant_chunks(SAMPLE_QUERY, top_k=3)
    print(f"  → Retrieved {len(results)} chunks\n")

    for i, r in enumerate(results):
        print(f"  Result {i + 1}  (similarity={r['similarity']:.4f})")
        print(f"    Title:   {r['title']}")
        print(f"    Source:  {r['source_url']}")
        content_preview = r["content"][:200].replace("\n", " ")
        print(f"    Content: {content_preview}...")
        print()

    print("=== Test complete ===\n")


if __name__ == "__main__":
    asyncio.run(main())
