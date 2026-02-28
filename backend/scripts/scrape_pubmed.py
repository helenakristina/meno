"""PubMed Central scraper for Meno RAG knowledge base.

Searches PubMed Central for menopause/perimenopause research articles,
fetches full text, extracts sections, and ingests them into the RAG knowledge base.

Uses NCBI E-utilities API (rate limited to 3 requests/second per NCBI policy).

Usage:
    cd backend
    uv run scripts/scrape_pubmed.py                    # full scrape (100 articles)
    uv run scripts/scrape_pubmed.py --dry-run          # preview only
    uv run scripts/scrape_pubmed.py --max-articles 10  # limit to 10 articles
    uv run scripts/scrape_pubmed.py --pmcid 7123456    # test single article
    uv run scripts/scrape_pubmed.py --reset-progress   # re-ingest all
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode

import httpx
import requests
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Suppress XMLParsedAsHTMLWarning — we intentionally use html.parser for NCBI API responses
# because it's more reliable than the xml parser for their XML format
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Resolve 'app.*' imports when running as a script from the backend directory
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.WARNING,  # Suppress internal logs — script uses print() for UX
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.core.supabase import get_client  # noqa: E402
from app.rag.ingest import (  # noqa: E402
    _COST_PER_1K_TOKENS,
    chunk_document,
    generate_embeddings,
    store_chunks,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Identifies us to NCBI; they request a descriptive user-agent
USER_AGENT = "MenoEducationalBot/1.0 (Health education app; not for commercial use)"

# Search query: menopause/perimenopause articles in PMC
# Uses simplified query since full text filters may not be available in all databases
# Note: The [sb] and [la] filters don't work reliably in PMC database searches
SEARCH_QUERY = "(menopause OR perimenopause)"

# Sections shorter than this are too thin to be useful for RAG
MIN_WORD_COUNT = 80

# Progress file: tracks which PMC IDs have been ingested to support retries
PROGRESS_FILE = Path(__file__).parent / "./data/scrape_pubmed_progress.json"

# NCBI rate limit: ~3 requests per second
RATE_LIMIT_DELAY = 0.4


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class ArticleMetadata(NamedTuple):
    """Basic article info from PubMed metadata."""

    pmc_id: str
    pmid: str | None
    title: str
    abstract: str | None
    pub_date: date | None
    url: str


class ArticleSection(NamedTuple):
    """One section of an article for ingestion."""

    pmc_id: str
    title: str
    section_name: str
    text: str
    word_count: int
    url: str
    pub_date: date | None

    @property
    def progress_key(self) -> str:
        """Unique key for progress tracking."""
        return f"{self.pmc_id}#{self.section_name}"


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------


def load_progress() -> set[str]:
    """Load previously processed PMC IDs from the progress file."""
    if PROGRESS_FILE.exists():
        data = json.loads(PROGRESS_FILE.read_text())
        return set(data.get("processed", []))
    return set()


def save_progress(processed: set[str]) -> None:
    """Persist processed PMC IDs so a retry can skip completed work."""
    PROGRESS_FILE.write_text(json.dumps({"processed": sorted(processed)}, indent=2))


# ---------------------------------------------------------------------------
# NCBI API functions
# ---------------------------------------------------------------------------


async def search_pubmed(
    query: str,
    max_results: int = 100,
    retstart: int = 0,
    session: httpx.AsyncClient | None = None,
) -> list[str]:
    """Search PubMed Central and return list of PMC IDs.

    Args:
        query: Search query (e.g., "menopause AND free full text").
        max_results: Max results to return per call (1-100000).
        retstart: Starting index for pagination.
        session: Optional httpx AsyncClient; creates one if None.

    Returns:
        List of PMC ID strings like ["7123456", "8234567", ...].
    """
    should_close = False
    if session is None:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
        should_close = True

    try:
        params = {
            "db": "pmc",
            "term": query,
            "retmax": max_results,
            "retstart": retstart,
            "rettype": "uilist",
            "retmode": "xml",
            "tool": "MenoBot",
        }

        url = f"{NCBI_BASE_URL}/esearch.fcgi?{urlencode(params)}"
        await asyncio.sleep(RATE_LIMIT_DELAY)

        response = await session.get(url, timeout=30)
        response.raise_for_status()

        # Parse XML response using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        id_elements = soup.find_all("id")
        ids = []
        for elem in id_elements:
            id_text = elem.get_text(strip=True)
            # Strip "PMC" prefix if present
            if id_text.startswith("PMC"):
                id_text = id_text[3:]
            ids.append(id_text)

        return ids

    finally:
        if should_close:
            await session.aclose()


async def fetch_article_metadata(
    pmc_id: str, session: httpx.AsyncClient
) -> ArticleMetadata | None:
    """Fetch article metadata from PubMed.

    Args:
        pmc_id: PubMed Central ID (e.g., "7123456" or "12944748").
        session: httpx AsyncClient.

    Returns:
        ArticleMetadata or None if fetch fails.
    """
    params = {
        "db": "pmc",
        "id": pmc_id,
        "rettype": "docsum",
        "retmode": "xml",
        "tool": "MenoBot",
    }

    url = f"{NCBI_BASE_URL}/esummary.fcgi?{urlencode(params)}"
    await asyncio.sleep(RATE_LIMIT_DELAY)

    try:
        response = await session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        docsum = soup.find("docsum")
        if not docsum:
            return None

        # Extract fields from docsum
        title_elem = docsum.find("item", {"name": "Title"})
        title = title_elem.get_text(strip=True) if title_elem else ""

        pub_date_elem = docsum.find("item", {"name": "PubDate"})
        pub_date_str = pub_date_elem.get_text(strip=True) if pub_date_elem else None
        pub_date = _parse_pubmed_date(pub_date_str)

        pmid_elem = docsum.find("item", {"name": "PMID"})
        pmid = pmid_elem.get_text(strip=True) if pmid_elem else None

        if not title:
            return None

        article_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/"

        return ArticleMetadata(
            pmc_id=pmc_id,
            pmid=pmid,
            title=title,
            abstract=None,  # Fetched separately
            pub_date=pub_date,
            url=article_url,
        )

    except Exception as e:
        print(f"    ✗ Failed to fetch metadata for PMC{pmc_id}: {e}")
        return None


def _parse_pubmed_date(date_str: str | None) -> date | None:
    """Parse PubMed date string (various formats) to date object."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try ISO format first (YYYY-MM-DD)
    if len(date_str) >= 10:
        try:
            parts = date_str.split("-")
            if len(parts) >= 3:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass

    # Try YYYY-MM format
    if len(date_str) >= 7:
        try:
            parts = date_str.split("-")
            if len(parts) >= 2:
                return date(int(parts[0]), int(parts[1]), 1)
        except (ValueError, IndexError):
            pass

    # Try just YYYY
    if len(date_str) >= 4:
        try:
            return date(int(date_str[:4]), 1, 1)
        except ValueError:
            pass

    return None


async def fetch_article_fulltext(
    pmc_id: str, session: httpx.AsyncClient
) -> dict[str, str] | None:
    """Fetch full-text article from PMC and extract sections.

    Attempts to retrieve and parse XML/HTML from PMC, extracting
    major sections: Abstract, Methods, Results, Discussion, Conclusion.

    Args:
        pmc_id: PubMed Central ID.
        session: httpx AsyncClient (not used for fulltext; requests library used instead).

    Returns:
        Dict mapping section names to text (e.g., {"abstract": "...", "methods": "..."})
        or None if unavailable.
    """
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/"

    await asyncio.sleep(RATE_LIMIT_DELAY)

    try:
        # Use requests library for fulltext (better compatibility with PMC website)
        # than httpx which can trigger bot detection
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Try parsing as HTML
        soup = BeautifulSoup(response.text, "html.parser")

        sections_dict = {}

        # Try to extract structured sections
        # Look for common section patterns in article containers
        article = soup.find("article") or soup.find("div", {"class": "article-text"})
        if not article:
            article = soup.body

        if article:
            # Extract abstract
            abstract_sec = article.find(
                "div", {"id": lambda x: x and "abstract" in x.lower()}
            )
            if abstract_sec:
                abstract_text = _extract_section_text(abstract_sec)
                if abstract_text:
                    sections_dict["abstract"] = abstract_text

            # Extract methods section
            methods_sec = article.find(
                "div",
                {
                    "id": lambda x: (
                        x and "s" in (x or "").lower() and "method" in x.lower()
                    )
                },
            )
            if methods_sec:
                methods_text = _extract_section_text(methods_sec)
                if methods_text:
                    sections_dict["methods"] = methods_text

            # Extract results section
            results_sec = article.find(
                "div", {"id": lambda x: x and "result" in (x or "").lower()}
            )
            if results_sec:
                results_text = _extract_section_text(results_sec)
                if results_text:
                    sections_dict["results"] = results_text

            # Extract discussion section
            discussion_sec = article.find(
                "div", {"id": lambda x: x and "discuss" in (x or "").lower()}
            )
            if discussion_sec:
                discussion_text = _extract_section_text(discussion_sec)
                if discussion_text:
                    sections_dict["discussion"] = discussion_text

            # If no structured sections found, try extracting all paragraphs
            if not sections_dict:
                # Fallback: extract all paragraphs as a single "full_text" section
                paragraphs = article.find_all("p", limit=100)
                if paragraphs:
                    text_parts = [
                        p.get_text(separator=" ", strip=True) for p in paragraphs
                    ]
                    text_parts = [t for t in text_parts if t]
                    if text_parts:
                        sections_dict["full_text"] = "\n\n".join(text_parts)

        return sections_dict if sections_dict else None

    except Exception as e:
        print(f"    ✗ Failed to fetch full text for PMC{pmc_id}: {e}")
        return None


def _extract_section_text(element) -> str:
    """Extract readable text from an HTML element."""
    text = element.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = " ".join(text.split())
    return text.strip() if text else ""


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_cost_from_text(text: str) -> float:
    """Rough cost estimate before chunking: chars / 4 ≈ tokens."""
    estimated_tokens = len(text) / 4
    return (estimated_tokens / 1000) * _COST_PER_1K_TOKENS


# ---------------------------------------------------------------------------
# Deduplication check
# ---------------------------------------------------------------------------


async def article_already_ingested(pmc_id: str) -> bool:
    """Check if article with this PMC ID already exists in RAG database.

    Args:
        pmc_id: PubMed Central ID.

    Returns:
        True if any chunks with this pmc_id exist; False otherwise.
    """
    try:
        client = await get_client()
        result = await client.from_("rag_documents").select(
            "pmc_id",
            count="exact"
        ).eq("pmc_id", pmc_id).execute()

        # If any rows exist with this pmc_id, article is already ingested
        return len(result.data) > 0
    except Exception as e:
        print(f"    ⚠️  Error checking if article ingested: {e}")
        return False


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


async def ingest_article_sections(
    metadata: ArticleMetadata,
    sections: dict[str, str],
    dry_run: bool,
) -> int:
    """Chunk, embed, and store article sections. Returns number of chunks created.

    Args:
        metadata: Article metadata.
        sections: Dict of section_name -> text.
        dry_run: If True, estimate cost but don't store.

    Returns:
        Total chunk count across all sections.
    """
    total_chunks = 0

    for section_name, text in sections.items():
        # Skip short sections
        word_count = len(text.split())
        if word_count < MIN_WORD_COUNT:
            continue

        # Chunk the section
        chunks = chunk_document(
            text=text,
            title=metadata.title,
            source_url=metadata.url,
            section_name=section_name,
        )

        if not chunks:
            continue

        if dry_run:
            cost = estimate_cost_from_text(text)
            print(
                f"    [dry-run] {section_name}: {len(chunks)} chunks, est. cost ${cost:.4f}"
            )
            total_chunks += len(chunks)
            continue

        # Generate embeddings and store
        try:
            texts = [c["content"] for c in chunks]
            embeddings = await generate_embeddings(texts)
            await store_chunks(
                chunks,
                embeddings,
                source_type="pubmed",
                publication_date=metadata.pub_date,
                pmc_id=metadata.pmc_id,
            )
            total_chunks += len(chunks)
        except Exception as e:
            print(f"    ✗ Failed to store {section_name}: {e}")
            raise

    return total_chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape PubMed Central for menopause research and ingest into RAG knowledge base.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/scrape_pubmed.py\n"
            "  uv run scripts/scrape_pubmed.py --max-articles 10\n"
            "  uv run scripts/scrape_pubmed.py --dry-run\n"
            "  uv run scripts/scrape_pubmed.py --pmcid 7123456\n"
            "  uv run scripts/scrape_pubmed.py --reset-progress\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--max-articles",
        "-n",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of articles to ingest (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and chunk but do not embed or store. Shows cost estimate.",
    )
    parser.add_argument(
        "--pmcid",
        metavar="PMCID",
        help="Test-scrape a single article by PMC ID (e.g., 7123456).",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Ignore saved progress and re-process all articles from scratch.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    args = parse_args()

    print("\n=== PubMed Central Scraper for Meno RAG ===")
    print(f"    Query:     {SEARCH_QUERY}")
    print(f"    Dry run:   {args.dry_run}")
    print(f"    Max:       {args.max_articles} articles")
    print()

    # Load progress
    processed: set[str] = set() if args.reset_progress else load_progress()
    if processed and not args.reset_progress:
        print(f"Resuming — {len(processed)} articles already ingested.\n")

    # Set up HTTP session with User-Agent and proper timeouts
    session = httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )

    try:
        # --- Single article test mode ---
        if args.pmcid:
            print(f"Testing single article: PMC{args.pmcid}\n")
            metadata = await fetch_article_metadata(args.pmcid, session)
            if metadata is None:
                print(f"✗ Failed to fetch metadata for PMC{args.pmcid}")
                return

            print(f"Title: {metadata.title}")
            print(f"URL:   {metadata.url}\n")

            sections = await fetch_article_fulltext(args.pmcid, session)
            if sections is None:
                print("✗ Failed to fetch full text")
                return

            print(f"Sections found: {', '.join(sections.keys())}\n")

            chunk_count = await ingest_article_sections(
                metadata, sections, args.dry_run
            )
            print(f"✓ Ingested {chunk_count} chunks\n")
            return

        # --- Full search mode ---
        print("Searching PubMed Central...", end=" ", flush=True)
        pmc_ids = await search_pubmed(SEARCH_QUERY, max_results=10000)
        print(f"found {len(pmc_ids)} articles")

        # Filter already-processed articles
        new_ids = [id for id in pmc_ids if id not in processed]
        ids_to_process = new_ids[: args.max_articles]
        skipped_limit = len(new_ids) - len(ids_to_process)

        print(f"\nTotal found:       {len(pmc_ids)}")
        print(f"New (unprocessed): {len(new_ids)}")
        print(f"Will process:      {len(ids_to_process)}")
        if skipped_limit:
            print(f"Deferred (limit):  {skipped_limit} (run again to continue)")

        if not ids_to_process:
            print("\nNothing to do. Use --reset-progress to re-ingest everything.")
            return

        # --- Cost estimation loop ---
        print("\nFetching metadata for cost estimation...", end=" ", flush=True)
        total_estimated_chars = 0
        articles_with_fulltext = 0

        for pmc_id in ids_to_process[:20]:  # Estimate from first 20
            metadata = await fetch_article_metadata(pmc_id, session)
            if metadata is None:
                continue

            sections = await fetch_article_fulltext(pmc_id, session)
            if sections is None:
                continue

            articles_with_fulltext += 1
            for text in sections.values():
                total_estimated_chars += len(text)

        print(f"done ({articles_with_fulltext} articles with full text)")

        if articles_with_fulltext == 0:
            print("⚠️  No articles with full text retrieved during estimation.")
            print(
                "    (This may be due to rate limiting. Ingestion will attempt full text for each article.)\n"
            )
            # Estimate based on typical article size instead of skipping
            # Average menopause paper: ~5000-8000 words
            estimated_words_per_article = 6000
            estimated_chars = estimated_words_per_article * 5  # Rough conversion
            total_estimated_chars = estimated_chars * len(ids_to_process)
        else:
            # Use actual estimation if we got full text samples
            pass

        # Extrapolate cost estimate
        avg_chars_per_article = total_estimated_chars / max(1, articles_with_fulltext)
        estimated_total_chars = avg_chars_per_article * len(ids_to_process)
        estimated_cost = estimate_cost_from_text("x" * int(estimated_total_chars))

        print(
            f"\nEstimated content: ~{int(estimated_total_chars / 4 / 1000):.0f}K tokens"
        )
        print(f"Embedding cost:    ~${estimated_cost:.4f}")

        if not args.dry_run:
            confirm = input("\nProceed with ingestion? (y/n): ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return

        # --- Ingest all articles ---
        print()
        total_chunks = 0
        errors = []
        skipped_count = 0

        for i, pmc_id in enumerate(ids_to_process, 1):
            # Skip if already processed (in case of concurrent runs)
            if pmc_id in processed:
                continue

            print(f"[{i}/{len(ids_to_process)}] PMC{pmc_id}", end=" ", flush=True)

            try:
                # Check if article already ingested in database
                if not args.dry_run and await article_already_ingested(pmc_id):
                    print("⊘ (already ingested)")
                    skipped_count += 1
                    processed.add(pmc_id)
                    save_progress(processed)
                    continue

                metadata = await fetch_article_metadata(pmc_id, session)
                if metadata is None:
                    print("✗ (failed to fetch metadata)")
                    errors.append((pmc_id, "metadata fetch failed"))
                    continue

                sections = await fetch_article_fulltext(pmc_id, session)
                if sections is None:
                    print("✗ (no full text)")
                    errors.append((pmc_id, "full text unavailable"))
                    continue

                chunk_count = await ingest_article_sections(
                    metadata, sections, args.dry_run
                )
                if not args.dry_run:
                    print(f"✓ {chunk_count} chunks")
                total_chunks += chunk_count

                processed.add(pmc_id)
                if not args.dry_run:
                    save_progress(processed)

            except Exception as e:
                print(f"✗ ({e})")
                errors.append((pmc_id, str(e)))
                logging.exception("Failed to ingest PMC%s", pmc_id)

        # --- Summary ---
        print(f"\n{'=' * 60}")
        mode = "dry-run" if args.dry_run else "ingested"
        success_count = len(ids_to_process) - len(errors) - skipped_count
        print(f"Done! Articles {mode}: {success_count}/{len(ids_to_process)}")
        print(f"      Chunks created:  {total_chunks}")
        if not args.dry_run and skipped_count:
            print(f"      Already ingested: {skipped_count}")
        if errors:
            print(f"      Errors:          {len(errors)}")
            for pmc_id, msg in errors[:10]:
                print(f"        - PMC{pmc_id}: {msg}")
            if len(errors) > 10:
                print(f"        ... and {len(errors) - 10} more")
        if not args.dry_run and PROGRESS_FILE.exists():
            print(f"      Progress saved:  {PROGRESS_FILE.name}")
        print()

    finally:
        await session.aclose()


if __name__ == "__main__":
    asyncio.run(main())
