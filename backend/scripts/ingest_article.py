"""Interactive script for manually ingesting articles into the RAG knowledge base.

Prompts for article metadata and text, chunks it, generates embeddings,
and stores results in rag_documents.

Usage:
    cd backend
    uv run scripts/ingest_article.py                        # interactive text paste
    uv run scripts/ingest_article.py --file abstract.txt    # read text from file
    uv run scripts/ingest_article.py -f /tmp/abstract.txt   # short flag
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

# Resolve 'app.*' imports when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.WARNING,  # Suppress info logs — script uses print() for UX
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.rag.ingest import (  # noqa: E402
    _COST_PER_1K_TOKENS,
    chunk_document,
    generate_embeddings,
    store_chunks,
)

VALID_SOURCE_TYPES = {"wiki", "pubmed", "guidelines"}


def prompt(label: str, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  (required — please enter a value)")


def prompt_multiline(label: str) -> str:
    print(f"{label} (press Enter twice when done):")
    lines: list[str] = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    # Strip trailing blank line used as sentinel
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def estimate_cost(chunks: list[dict]) -> float:
    total_chars = sum(len(c["content"]) for c in chunks)
    estimated_tokens = total_chars / 4
    return (estimated_tokens / 1000) * _COST_PER_1K_TOKENS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually ingest an article into the Meno RAG knowledge base.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/ingest_article.py\n"
            "  uv run scripts/ingest_article.py --file abstract.txt\n"
            "  uv run scripts/ingest_article.py -f /tmp/article.txt"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        "-f",
        metavar="PATH",
        help="Path to a text file containing the article body. "
        "If omitted, you will be prompted to paste text interactively.",
    )
    return parser.parse_args()


def read_file(path: str) -> str:
    file = Path(path)
    if not file.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        print(f"Error: file is empty: {path}")
        sys.exit(1)
    return text


async def main() -> None:
    args = parse_args()

    print("\n=== Meno RAG Article Ingestion ===\n")

    # --- Collect metadata ---
    title = prompt("Title")
    source_url = prompt("Source URL")

    while True:
        source_type = prompt(
            f"Source type ({'/'.join(sorted(VALID_SOURCE_TYPES))})"
        ).lower()
        if source_type in VALID_SOURCE_TYPES:
            break
        print(f"  (must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))})")

    pub_date_str = prompt("Publication date (YYYY-MM-DD, optional)", required=False)
    publication_date: date | None = None
    if pub_date_str:
        try:
            publication_date = date.fromisoformat(pub_date_str)
        except ValueError:
            print(f"  Invalid date '{pub_date_str}' — skipping publication date.")

    if args.file:
        text = read_file(args.file)
        print(f"\nReading text from: {args.file}")
    else:
        text = prompt_multiline("\nPaste article text")
        if not text.strip():
            print("No text provided. Exiting.")
            sys.exit(1)

    # --- Chunk ---
    print("\nChunking...", end=" ", flush=True)
    chunks = chunk_document(text=text, title=title, source_url=source_url)
    cost_estimate = estimate_cost(chunks)
    print(
        f"done\nFound {len(chunks)} chunk{'s' if len(chunks) != 1 else ''}. Estimated cost: ${cost_estimate:.4f}"
    )

    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # --- Embed ---
    print("Embedding...", end=" ", flush=True)
    texts = [c["content"] for c in chunks]
    embeddings = await generate_embeddings(texts)
    print("done")

    # --- Store ---
    print("Storing...", end=" ", flush=True)
    await store_chunks(
        chunks, embeddings, source_type=source_type, publication_date=publication_date
    )
    print("done")

    print(
        f"\nSuccessfully ingested {len(chunks)} chunk{'s' if len(chunks) != 1 else ''}!"
    )
    print(f"  Title:       {title}")
    print(f"  Source:      {source_url}")
    print(f"  Type:        {source_type}")
    if publication_date:
        print(f"  Published:   {publication_date}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
