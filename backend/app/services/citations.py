"""Citation extraction and sanitization service for Ask Meno responses.

Handles phantom citation removal, renumbering, and extraction of Citation objects
from LLM responses. All functions are pure (no side effects, no external dependencies).
"""

import logging
import re
from typing import NamedTuple

from app.models.chat import Citation

logger = logging.getLogger(__name__)


class CitationExtractResult(NamedTuple):
    """Result of citation sanitization: cleaned text and list of removed indices."""

    text: str
    removed_indices: list[int]


class CitationService:
    """Service for extracting and sanitizing citations from LLM responses.

    Responsibilities:
    - Remove phantom citations (references beyond available sources)
    - Renumber valid citations to match extraction order
    - Extract Citation objects with section context

    All methods are pure functions with no external dependencies.
    """

    def sanitize_and_renumber(
        self, response_text: str, max_valid_sources: int
    ) -> CitationExtractResult:
        """Remove invalid citations and renumber valid ones to match extracted citations.

        Process:
        1. Identify all citations in the text (both [Source N] and [N] formats)
        2. Remove citations that reference sources beyond max_valid_sources (phantom citations)
        3. Renumber remaining citations to 1, 2, 3... to match the extraction order

        This ensures citation numbers in the text always match the SOURCES section.

        Args:
            response_text: Raw response from LLM
            max_valid_sources: Number of unique chunks that were shown in the prompt (post-dedup)

        Returns:
            CitationExtractResult with cleaned_text and removed_indices
        """
        removed_indices: list[int] = []
        cleaned_text = response_text

        # First, find all citation indices that actually appear in the text
        found_indices: set[int] = set()
        for match in re.finditer(r"\[Source (\d+)\]", cleaned_text):
            found_indices.add(int(match.group(1)))
        for match in re.finditer(r"(?<![\/\w])\[(\d+)\](?![\w])", cleaned_text):
            start = match.start()
            if start == 0 or cleaned_text[start - 1] in (
                " ",
                ".",
                ":",
                ";",
                ",",
                ")",
                "—",
            ):
                found_indices.add(int(match.group(1)))

        # Separate valid citations from phantom ones
        valid_indices = sorted([i for i in found_indices if 1 <= i <= max_valid_sources])
        phantom_indices = [i for i in found_indices if i > max_valid_sources]

        # Remove phantom citations
        for source_num in phantom_indices:
            pattern = f"[Source {source_num}]"
            while pattern in cleaned_text:
                cleaned_text = cleaned_text.replace(pattern, "", 1)
                removed_indices.append(source_num)

            pattern = f"[{source_num}]"
            while pattern in cleaned_text:
                cleaned_text = cleaned_text.replace(pattern, "", 1)
                if source_num not in removed_indices:
                    removed_indices.append(source_num)

        # Renumber valid citations to 1, 2, 3, ... to match extraction order
        # Map old index -> new index
        renumber_map = {
            old_idx: new_idx for new_idx, old_idx in enumerate(valid_indices, start=1)
        }

        # Apply renumbering in reverse order to avoid position shifts
        for old_idx in sorted(renumber_map.keys(), reverse=True):
            new_idx = renumber_map[old_idx]
            if old_idx != new_idx:
                # Renumber [Source N] format
                pattern = f"[Source {old_idx}]"
                cleaned_text = cleaned_text.replace(pattern, f"[Source {new_idx}]")

                # Renumber plain [N] format
                # Use word boundaries to avoid replacing [11] when looking for [1]
                cleaned_text = re.sub(
                    rf"(?<![\/\w])\[{old_idx}\](?![\w\d])", f"[{new_idx}]", cleaned_text
                )

        # Clean up extra whitespace
        cleaned_text = re.sub(r"\s+([.,:;!?])", r"\1", cleaned_text)
        cleaned_text = re.sub(r" {2,}", " ", cleaned_text)

        if removed_indices:
            logger.warning(
                "Removed phantom citations: %s (max valid sources: %d)",
                sorted(set(removed_indices)),
                max_valid_sources,
            )

        if any(renumber_map[old] != old for old in renumber_map):
            logger.info(
                "Renumbered citations: %s",
                {
                    old: renumber_map[old]
                    for old in renumber_map
                    if renumber_map[old] != old
                },
            )

        return CitationExtractResult(text=cleaned_text, removed_indices=removed_indices)

    def extract(self, response_text: str, chunks: list[dict]) -> list[Citation]:
        """Map [Source N] or [N] references in the response to Citation objects with section context.

        Parses [Source 1], [Source 2], etc. OR [1], [2], etc. and maps them to the corresponding
        chunk's source_url and title. Includes section_name if available in chunk metadata.
        References beyond the available chunks are silently ignored (should be removed by
        sanitize_and_renumber first).

        Args:
            response_text: The response text containing citation references
            chunks: List of chunk dicts with keys: source_url, title, section_name (optional)

        Returns:
            List of Citation objects in order they appear in the response
        """
        # Find which citations are actually used in the response
        found_indices: set[int] = set()
        # Match both [Source N] and plain [N] formats
        for match in re.finditer(r"\[Source (\d+)\]", response_text):
            found_indices.add(int(match.group(1)))
        for match in re.finditer(r"(?<![\/\w])\[(\d+)\](?![\w])", response_text):
            # Extra check: only treat as citation if preceded by appropriate context
            start = match.start()
            if start == 0 or response_text[start - 1] in (
                " ",
                ".",
                ":",
                ";",
                ",",
                ")",
                "—",
            ):
                found_indices.add(int(match.group(1)))

        citations: list[Citation] = []

        for idx in sorted(found_indices):
            chunk_index = idx - 1  # Source N is 1-indexed
            if 0 <= chunk_index < len(chunks):
                chunk = chunks[chunk_index]
                url = chunk.get("source_url", "")
                title = chunk.get("title", "")
                section = chunk.get("section_name")  # May be None

                if url:
                    citations.append(
                        Citation(url=url, title=title, section=section, source_index=idx)
                    )

        return citations
