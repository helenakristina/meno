"""Web scraper for The Menopause Wiki (menopausewiki.ca).

Scrapes all pages on the wiki, splits content by H2 sections, and ingests
each section into the RAG knowledge base via the existing ingest pipeline.

robots.txt status: scraping allowed for all bots except GPTBot.
Our user-agent identifies us as an educational bot (not GPTBot).

Usage:
    cd backend
    uv run scripts/scrape_menopause_wiki.py                    # full scrape
    uv run scripts/scrape_menopause_wiki.py --dry-run          # preview only
    uv run scripts/scrape_menopause_wiki.py --max-articles 10  # limit sections
    uv run scripts/scrape_menopause_wiki.py --url https://menopausewiki.ca/fitness/
    uv run scripts/scrape_menopause_wiki.py --reset-progress   # re-ingest all
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# Resolve 'app.*' imports when running as a script from the backend directory
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.WARNING,  # Suppress internal logs — script uses print() for UX
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.rag.ingest import (  # noqa: E402
    _COST_PER_1K_TOKENS,
    chunk_document,
    generate_embeddings,
    store_chunks,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://menopausewiki.ca"

# Identifies us to the site; not GPTBot so robots.txt allows access
USER_AGENT = "MenoEducationalBot/1.0 (Health education app; not for commercial use)"

# Pages to scrape, in priority order (highest-value content first)
WIKI_PAGES = [
    "/",                        # Main wiki — 170k chars, 10 H2 sections
    "/is-this-perimenopause/",  # Perimenopause guide
    "/resources/",              # Research and resource links
    "/fitness/",                # Exercise and fitness
]

# Skip provider directory — it's a directory listing, not educational content
SKIP_PAGES = {"/providers/"}

# Sections shorter than this are too thin to be useful for RAG
MIN_WORD_COUNT = 80

# Progress file: tracks which sections have been ingested to support retries
PROGRESS_FILE = Path(__file__).parent / ".scrape_progress.json"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class ScrapedSection(NamedTuple):
    page_title: str       # H1 of the page (e.g. "The Menopause Wiki")
    section_name: str | None  # H2 text, or None for intro/single-page
    url: str              # Full URL of the page
    text: str             # Extracted plain text
    word_count: int       # Approximate word count for filtering

    @property
    def progress_key(self) -> str:
        """Unique key for progress tracking."""
        return f"{self.url}#{self.section_name or '__intro__'}"

    @property
    def display_label(self) -> str:
        return self.section_name or "(intro)"


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------


def load_progress() -> set[str]:
    """Load previously processed section keys from the progress file."""
    if PROGRESS_FILE.exists():
        data = json.loads(PROGRESS_FILE.read_text())
        return set(data.get("processed", []))
    return set()


def save_progress(processed: set[str]) -> None:
    """Persist processed section keys so a retry can skip completed work."""
    PROGRESS_FILE.write_text(json.dumps({"processed": sorted(processed)}, indent=2))


# ---------------------------------------------------------------------------
# Fetching and parsing
# ---------------------------------------------------------------------------


def fetch_page(url: str, session: requests.Session) -> BeautifulSoup | None:
    """Fetch a URL and return a parsed BeautifulSoup tree, or None on failure."""
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"  ✗ Failed to fetch {url}: {e}")
        return None


def _element_text(element: Tag) -> str:
    """Extract readable plain text from a block element.

    Joins child text with spaces, collapses whitespace. Suitable for
    paragraphs, list items, headings, etc.
    """
    return " ".join(element.get_text(separator=" ").split())


def split_page_into_sections(soup: BeautifulSoup, page_url: str) -> list[ScrapedSection]:
    """Split a wiki page into one ScrapedSection per H2 heading.

    The main wiki page is 170k characters with 10 major H2 sections — splitting
    by H2 gives us manageable chunks with meaningful section_name metadata.

    For pages with no H2 headings, the whole page becomes one section.
    """
    content = soup.select_one("#content")
    if not content:
        print(f"  ✗ No #content element found — page structure may have changed")
        return []

    h1 = content.select_one("h1")
    page_title = h1.get_text(strip=True) if h1 else "The Menopause Wiki"

    sections: list[ScrapedSection] = []
    h2_elements = content.find_all("h2")

    # --- Pages with no H2: ingest as a single document ---
    if not h2_elements:
        text = _extract_content_text(content, skip_tags={"h1", "nav"})
        word_count = len(text.split())
        if word_count >= MIN_WORD_COUNT:
            sections.append(
                ScrapedSection(
                    page_title=page_title,
                    section_name=None,
                    url=page_url,
                    text=text,
                    word_count=word_count,
                )
            )
        return sections

    # --- Capture intro content (everything before the first H2) ---
    intro_parts: list[str] = []
    for node in content.children:
        if isinstance(node, NavigableString):
            continue
        if node.name == "h2":
            break
        if node.name in ("p", "ul", "ol", "blockquote"):
            text = _element_text(node)
            if text:
                intro_parts.append(text)

    if intro_parts:
        intro_text = "\n\n".join(intro_parts)
        word_count = len(intro_text.split())
        if word_count >= MIN_WORD_COUNT:
            sections.append(
                ScrapedSection(
                    page_title=page_title,
                    section_name="Introduction",
                    url=page_url,  # Intro has no anchor — link to top of page
                    text=intro_text,
                    word_count=word_count,
                )
            )

    # --- One section per H2 ---
    for h2 in h2_elements:
        section_name = h2.get_text(strip=True)

        # Skip pure navigation sections
        if "table of contents" in section_name.lower():
            continue

        # Build a direct anchor URL so each chunk links to its exact section.
        # Prefer the element's id attribute (already URL-safe, e.g. "introduction").
        # Fall back to URL-encoding the section name (spaces → %20).
        h2_id = h2.get("id", "").strip()
        anchor = h2_id if h2_id else quote(section_name, safe="")
        section_url = f"{page_url}#{anchor}"

        parts: list[str] = []
        for sibling in h2.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if sibling.name == "h2":
                break  # Next section starts
            if sibling.name in ("p", "ul", "ol", "h3", "h4", "h5", "blockquote", "div"):
                text = _element_text(sibling)
                if text:
                    parts.append(text)

        if not parts:
            continue

        section_text = "\n\n".join(parts)
        word_count = len(section_text.split())

        if word_count < MIN_WORD_COUNT:
            print(f"    ⚡ Skipping '{section_name[:60]}' — only {word_count} words")
            continue

        sections.append(
            ScrapedSection(
                page_title=page_title,
                section_name=section_name,
                url=section_url,
                text=section_text,
                word_count=word_count,
            )
        )

    return sections


def _extract_content_text(content: Tag, skip_tags: set[str]) -> str:
    """Extract text from all block elements in content, skipping listed tags."""
    parts: list[str] = []
    for node in content.descendants:
        if isinstance(node, NavigableString):
            continue
        if node.name in skip_tags:
            continue
        if node.name in ("p", "li", "h2", "h3", "h4", "h5", "blockquote"):
            text = _element_text(node)
            if text:
                parts.append(text)
    # Deduplicate consecutive identical lines (descendant traversal can repeat)
    seen: list[str] = []
    for p in parts:
        if not seen or p != seen[-1]:
            seen.append(p)
    return "\n\n".join(seen)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_cost_from_text(text: str) -> float:
    """Rough cost estimate before chunking: chars / 4 ≈ tokens."""
    estimated_tokens = len(text) / 4
    return (estimated_tokens / 1000) * _COST_PER_1K_TOKENS


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


async def ingest_section(section: ScrapedSection, dry_run: bool) -> int:
    """Chunk, embed, and store one section. Returns number of chunks created."""
    chunks = chunk_document(
        text=section.text,
        title=section.page_title,
        source_url=section.url,
        section_name=section.section_name,
    )

    if not chunks:
        return 0

    if dry_run:
        cost = estimate_cost_from_text(section.text)
        print(f"    [dry-run] {len(chunks)} chunks, est. cost ${cost:.4f}")
        return len(chunks)

    texts = [c["content"] for c in chunks]
    embeddings = await generate_embeddings(texts)
    await store_chunks(chunks, embeddings, source_type="wiki", publication_date=None)
    return len(chunks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape The Menopause Wiki and ingest sections into the RAG knowledge base.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/scrape_menopause_wiki.py\n"
            "  uv run scripts/scrape_menopause_wiki.py --max-articles 10\n"
            "  uv run scripts/scrape_menopause_wiki.py --dry-run\n"
            "  uv run scripts/scrape_menopause_wiki.py --url https://menopausewiki.ca/fitness/\n"
            "  uv run scripts/scrape_menopause_wiki.py --reset-progress\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--max-articles",
        "-n",
        type=int,
        default=50,
        metavar="N",
        help="Maximum number of sections to ingest (default: 50).",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.5,
        metavar="SECS",
        help="Seconds to wait between page fetches (default: 1.5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and chunk but do not embed or store. Shows cost estimate.",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Test-scrape a single URL instead of the full site.",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Ignore saved progress and re-process all pages from scratch.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    args = parse_args()

    print("\n=== Menopause Wiki Scraper ===")
    print(f"    Site:      {BASE_URL}")
    print(f"    Dry run:   {args.dry_run}")
    print(f"    Max:       {args.max_articles} sections")
    print(f"    Delay:     {args.delay}s between pages\n")

    # Load progress
    processed: set[str] = set() if args.reset_progress else load_progress()
    if processed and not args.reset_progress:
        print(f"Resuming — {len(processed)} sections already ingested.\n")

    # Build the list of pages to fetch
    if args.url:
        path = urlparse(args.url).path
        pages_to_fetch = [path]
    else:
        pages_to_fetch = [p for p in WIKI_PAGES if p not in SKIP_PAGES]

    # Set up HTTP session
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # --- Fetch and parse all pages ---
    all_sections: list[ScrapedSection] = []

    for i, path in enumerate(pages_to_fetch):
        url = BASE_URL + path
        print(f"Fetching {url}...", end=" ", flush=True)

        soup = fetch_page(url, session)
        if soup is None:
            continue

        sections = split_page_into_sections(soup, url)
        print(f"{len(sections)} sections found")
        for s in sections:
            label = s.display_label[:60]
            print(f"    {label:<62} {s.word_count:>5} words")

        all_sections.extend(sections)

        # Polite delay between pages (skip after last page)
        if i < len(pages_to_fetch) - 1:
            time.sleep(args.delay)

    if not all_sections:
        print("\nNo sections found — check that the site is accessible.")
        return

    # --- Filter already-processed sections ---
    new_sections = [s for s in all_sections if s.progress_key not in processed]
    sections_to_process = new_sections[: args.max_articles]
    skipped_limit = len(new_sections) - len(sections_to_process)

    print(f"\nTotal sections:    {len(all_sections)}")
    print(f"New (unprocessed): {len(new_sections)}")
    print(f"Will process:      {len(sections_to_process)}")
    if skipped_limit:
        print(f"Deferred (limit):  {skipped_limit} (run again to continue)")

    if not sections_to_process:
        print("\nNothing to do. Use --reset-progress to re-ingest everything.")
        return

    # --- Cost estimate ---
    total_chars = sum(len(s.text) for s in sections_to_process)
    total_words = sum(s.word_count for s in sections_to_process)
    cost_estimate = estimate_cost_from_text("x" * total_chars)

    print(f"\nContent to ingest: ~{total_words:,} words ({total_chars:,} chars)")
    print(f"Embedding cost:    ~${cost_estimate:.4f}")

    if not args.dry_run:
        confirm = input("\nProceed with ingestion? (y/n): ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    # --- Ingest each section ---
    print()
    total_chunks = 0
    errors = 0

    for i, section in enumerate(sections_to_process, 1):
        label = f"{section.page_title} — {section.display_label}"
        print(f"[{i}/{len(sections_to_process)}] {label[:70]}")

        try:
            chunk_count = await ingest_section(section, args.dry_run)
            total_chunks += chunk_count
            if not args.dry_run:
                print(f"    ✓ {chunk_count} chunks stored")

            processed.add(section.progress_key)
            if not args.dry_run:
                save_progress(processed)  # Save after each section for crash recovery

        except Exception as e:
            errors += 1
            print(f"    ✗ Failed: {e}")
            logging.exception(
                "Ingestion failed for %s / %s", section.url, section.section_name
            )

    # --- Summary ---
    print(f"\n{'=' * 50}")
    mode = "dry-run" if args.dry_run else "ingested"
    print(f"Done! Sections {mode}: {len(sections_to_process) - errors}/{len(sections_to_process)}")
    print(f"      Chunks created:  {total_chunks}")
    if errors:
        print(f"      Errors:          {errors} (check logs)")
    if not args.dry_run and PROGRESS_FILE.exists():
        print(f"      Progress saved:  {PROGRESS_FILE.name}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
