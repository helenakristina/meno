"""Prune low-value PubMed chunks from the RAG database.

Runs all starter prompt questions against pgvector to identify which PubMed chunks
are actually relevant to real user queries. Deletes PubMed chunks that never score
above the similarity threshold for any query.

Non-PubMed sources (Menopause Wiki, etc.) are never touched.

Usage:
    # Dry run — see what would be deleted without deleting anything
    uv run scripts/prune_pubmed_chunks.py --dry-run

    # Actually delete
    uv run scripts/prune_pubmed_chunks.py

    # Custom similarity threshold (default 0.25)
    uv run scripts/prune_pubmed_chunks.py --threshold 0.30

    # Custom top-k per query (default 20)
    uv run scripts/prune_pubmed_chunks.py --top-k 30
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.supabase import get_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"


def load_starter_prompts(config_path: str | Path | None = None) -> list[str]:
    """Load all starter prompts from the config file into a flat list."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "starter_prompts.json"

    with open(config_path) as f:
        data = json.load(f)

    prompts = []
    for symptom, questions in data.get("starter_prompts", {}).items():
        prompts.extend(questions)

    logger.info(f"Loaded {len(prompts)} starter prompts from {config_path}")
    return prompts


async def get_embedding(client: AsyncOpenAI, text: str) -> list[float]:
    """Get embedding for a single text string."""
    normalized = text.replace("-", " ")
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=normalized)
    return response.data[0].embedding


async def find_useful_chunks(
    prompts: list[str],
    top_k: int = 20,
    threshold: float = 0.25,
) -> set[str]:
    """Run all prompts against pgvector and collect IDs of chunks that score well.

    Args:
        prompts: List of query strings to test
        top_k: How many chunks to retrieve per query
        threshold: Minimum similarity score to consider a chunk "useful"

    Returns:
        Set of chunk IDs (UUIDs as strings) that scored above threshold for at least one query
    """
    supabase = await get_client()
    openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    useful_ids: set[str] = set()
    total_prompts = len(prompts)

    for i, prompt in enumerate(prompts, 1):
        logger.info(f"[{i}/{total_prompts}] Querying: {prompt[:80]}...")

        try:
            embedding = await get_embedding(openai_client, prompt)

            result = await supabase.rpc(
                "match_rag_documents",
                {
                    "query_embedding": str(embedding),
                    "match_count": top_k,
                },
            ).execute()

            chunks = result.data or []

            relevant = [
                c
                for c in chunks
                if c.get("similarity", 0) >= threshold
                and c.get("source_type") == "pubmed"
            ]

            for chunk in relevant:
                useful_ids.add(chunk["id"])

            if relevant:
                logger.info(
                    f"  → {len(relevant)} useful PubMed chunks "
                    f"(top: {relevant[0].get('title', 'untitled')[:60]} "
                    f"sim={relevant[0].get('similarity', 0):.3f})"
                )
            else:
                logger.info("  → No PubMed chunks above threshold")

        except Exception as exc:
            logger.error(f"  → Error: {exc}")
            continue

    logger.info(f"\nTotal useful PubMed chunk IDs: {len(useful_ids)}")
    return useful_ids


async def get_pubmed_stats() -> dict:
    """Get counts of PubMed vs non-PubMed chunks."""
    supabase = await get_client()

    # Count all chunks
    all_result = (
        await supabase.table("rag_documents").select("id", count="exact").execute()
    )
    total = all_result.count or 0

    # Count PubMed chunks
    pubmed_result = (
        await supabase.table("rag_documents")
        .select("id", count="exact")
        .eq("source_type", "pubmed")
        .execute()
    )
    pubmed = pubmed_result.count or 0

    return {
        "total": total,
        "pubmed": pubmed,
        "non_pubmed": total - pubmed,
    }


async def delete_useless_chunks(
    useful_ids: set[str],
    dry_run: bool = True,
) -> int:
    """Delete PubMed chunks that aren't in the useful set.

    Args:
        useful_ids: Set of chunk IDs to KEEP
        dry_run: If True, only count what would be deleted

    Returns:
        Number of chunks deleted (or that would be deleted in dry run)
    """
    supabase = await get_client()

    # Fetch all PubMed chunk IDs
    logger.info("Fetching all PubMed chunk IDs...")
    all_pubmed = []
    offset = 0
    batch_size = 1000

    while True:
        result = (
            await supabase.table("rag_documents")
            .select("id")
            .eq("source_type", "pubmed")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        batch = result.data or []
        all_pubmed.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size

    all_pubmed_ids = {row["id"] for row in all_pubmed}
    to_delete = all_pubmed_ids - useful_ids

    logger.info(f"Total PubMed chunks: {len(all_pubmed_ids)}")
    logger.info(f"Useful PubMed chunks: {len(useful_ids)}")
    logger.info(f"Chunks to delete: {len(to_delete)}")

    if dry_run:
        logger.info("\n🔍 DRY RUN — no chunks were deleted.")
        logger.info(f"Would free approximately {len(to_delete) * 0.02:.1f} MB")
        logger.info("Run without --dry-run to actually delete.")
        return len(to_delete)

    # Delete in batches
    delete_list = list(to_delete)
    deleted = 0
    batch_size = 100

    for i in range(0, len(delete_list), batch_size):
        batch = delete_list[i : i + batch_size]
        try:
            await supabase.table("rag_documents").delete().in_("id", batch).execute()
            deleted += len(batch)
            if deleted % 500 == 0 or deleted == len(delete_list):
                logger.info(f"  Deleted {deleted}/{len(delete_list)} chunks...")
        except Exception as exc:
            logger.error(f"  Error deleting batch at offset {i}: {exc}")
            continue

    logger.info(f"\n✅ Deleted {deleted} PubMed chunks")
    return deleted


async def main(
    dry_run: bool = True,
    threshold: float = 0.25,
    top_k: int = 20,
    config_path: str | Path | None = None,
):
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Show current state
    logger.info("=" * 60)
    logger.info("RAG Database Pruning — PubMed chunks only")
    logger.info("=" * 60)

    stats = await get_pubmed_stats()
    logger.info(f"Total chunks: {stats['total']}")
    logger.info(f"PubMed chunks: {stats['pubmed']} (candidates for pruning)")
    logger.info(f"Non-PubMed chunks: {stats['non_pubmed']} (protected)")
    logger.info(f"Similarity threshold: {threshold}")
    logger.info(f"Top-k per query: {top_k}")
    logger.info("")

    # Load prompts
    prompts = load_starter_prompts(config_path)

    # Find useful chunks
    useful_ids = await find_useful_chunks(prompts, top_k=top_k, threshold=threshold)

    # Delete useless chunks
    logger.info("")
    await delete_useless_chunks(useful_ids, dry_run=dry_run)

    # Show final state
    if not dry_run:
        final_stats = await get_pubmed_stats()
        logger.info("\nFinal state:")
        logger.info(f"  Total chunks: {final_stats['total']}")
        logger.info(f"  PubMed chunks: {final_stats['pubmed']}")
        logger.info(f"  Non-PubMed chunks: {final_stats['non_pubmed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prune low-value PubMed chunks from RAG database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.25,
        help="Minimum similarity score to consider a chunk useful (default: 0.25)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of chunks to retrieve per query (default: 20)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to starter_prompts.json (default: backend/config/starter_prompts.json)",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            dry_run=args.dry_run,
            threshold=args.threshold,
            top_k=args.top_k,
            config_path=args.config,
        )
    )
