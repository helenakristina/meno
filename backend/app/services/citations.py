"""Citation extraction and sanitization service for Ask Meno responses.

Handles phantom citation removal, renumbering, relevance verification, and
extraction of Citation objects from LLM responses. All functions are pure
(no side effects, no external dependencies).
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
    - Verify that cited sources actually support nearby claims (relevance check)
    - Renumber valid citations to match extraction order
    - Extract Citation objects with section context

    All methods are pure functions with no external dependencies.
    """

    # ------------------------------------------------------------------
    # Relevance verification config
    # ------------------------------------------------------------------
    # Minimum fraction of non-stopword tokens from the claim sentence that
    # must appear in the cited chunk's content. If fewer than this fraction
    # match, the citation is considered unsupported and is stripped.
    #
    # This is a lightweight keyword-overlap heuristic — not a full semantic
    # check — but it catches the most common failure mode: the LLM generates
    # a claim from training data (e.g. "ashwagandha may help") and attaches
    # a citation to a source that discusses a related but different topic
    # (e.g. muscle protein turnover during menopause).
    #
    # Tuning:
    #   0.0  = disabled (no relevance checking)
    #   0.15 = lenient — only strips citations with near-zero overlap
    #   0.25 = moderate — good starting point
    #   0.40 = strict — may strip some valid citations with paraphrased claims
    _RELEVANCE_MIN_OVERLAP: float = 0.20

    _STOPWORDS: frozenset = frozenset(
        {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "can",
            "could",
            "should",
            "may",
            "might",
            "that",
            "this",
            "it",
            "its",
            "i",
            "my",
            "me",
            "we",
            "our",
            "you",
            "your",
            "they",
            "their",
            "what",
            "how",
            "when",
            "where",
            "which",
            "who",
            "some",
            "also",
            "about",
            "these",
            "those",
            "such",
            "help",
            "include",
            "including",
            "common",
            "options",
            "various",
            "certain",
            "many",
            "other",
        }
    )

    def _claim_source_overlap(self, claim_text: str, source_content: str) -> float:
        """Compute keyword overlap between a claim and a source chunk.

        Returns the fraction of meaningful claim tokens (len >= 3, not stopwords)
        that appear anywhere in the source content. This is intentionally simple
        and fast — it runs once per citation, not once per chunk.

        Args:
            claim_text: The sentence or phrase surrounding the citation.
            source_content: The full text of the cited chunk.

        Returns:
            Float between 0.0 and 1.0. Higher = more overlap.
        """
        claim_tokens = [
            t
            for t in re.split(r"\W+", claim_text.lower())
            if len(t) >= 3 and t not in self._STOPWORDS
        ]
        if not claim_tokens:
            return 1.0  # No meaningful tokens — can't judge, so allow it

        source_lower = source_content.lower()
        matches = sum(1 for t in claim_tokens if t in source_lower)
        return matches / len(claim_tokens)

    def _extract_claim_context(
        self, text: str, match_start: int, match_end: int
    ) -> str:
        """Extract the sentence surrounding a citation marker for relevance checking.

        Looks backward to the nearest sentence boundary and forward to the next one,
        returning the text that the citation is meant to support.

        Args:
            text: Full response text.
            match_start: Start index of the citation marker (e.g. "[Source 2]").
            match_end: End index of the citation marker.

        Returns:
            The sentence or clause containing/preceding the citation.
        """
        # Look backward for sentence start (period, newline, or start of text)
        search_start = max(0, match_start - 500)
        before = text[search_start:match_start]
        sentence_break = max(
            before.rfind(". "),
            before.rfind(".\n"),
            before.rfind("! "),
            before.rfind("? "),
            before.rfind("\n\n"),
        )
        if sentence_break >= 0:
            claim_start = search_start + sentence_break + 2
        else:
            claim_start = search_start

        # Look forward for sentence end
        search_end = min(len(text), match_end + 200)
        after = text[match_end:search_end]
        next_break = -1
        for sep in [". ", ".\n", "! ", "? ", "\n\n"]:
            pos = after.find(sep)
            if pos >= 0 and (next_break < 0 or pos < next_break):
                next_break = pos
        if next_break >= 0:
            claim_end = match_end + next_break + 1
        else:
            claim_end = search_end

        return text[claim_start:claim_end].strip()

    def verify_citations(
        self, response_text: str, chunks: list[dict]
    ) -> tuple[str, list[int]]:
        """Strip citations where the surrounding claim has low overlap with the source.

        Scans for every [Source N] or [N] marker, extracts the sentence around it,
        and checks whether the claim's keywords appear in the cited chunk. If
        overlap is below _RELEVANCE_MIN_OVERLAP, the citation marker is removed.

        This catches the most common misattribution pattern: the LLM generates a
        claim from its training data and attaches a citation to the nearest
        topically-related source, even though that source says nothing about the
        specific claim.

        Args:
            response_text: LLM response with citation markers.
            chunks: The RAG chunks that were passed to the LLM (in order).

        Returns:
            Tuple of (cleaned_text, list_of_stripped_source_indices).
        """
        if self._RELEVANCE_MIN_OVERLAP <= 0.0:
            return response_text, []

        stripped_indices: list[int] = []
        # Process in reverse order so removals don't shift positions
        # Collect all citation matches first
        pattern = re.compile(r"\[Source (\d+)\]|\[(\d+)\]")
        matches = list(pattern.finditer(response_text))

        for match in reversed(matches):
            source_num = int(match.group(1) or match.group(2))
            chunk_idx = source_num - 1

            if chunk_idx < 0 or chunk_idx >= len(chunks):
                continue  # Phantom citation — handled by sanitize_and_renumber

            chunk_content = chunks[chunk_idx].get("content", "")
            claim_text = self._extract_claim_context(
                response_text, match.start(), match.end()
            )
            overlap = self._claim_source_overlap(claim_text, chunk_content)

            if overlap < self._RELEVANCE_MIN_OVERLAP:
                logger.warning(
                    "Citation relevance check FAILED: [Source %d] overlap=%.2f "
                    "(threshold=%.2f) claim='%s' source_title='%s'",
                    source_num,
                    overlap,
                    self._RELEVANCE_MIN_OVERLAP,
                    claim_text[:120],
                    chunks[chunk_idx].get("title", "untitled")[:60],
                )
                # Remove the citation marker
                response_text = (
                    response_text[: match.start()] + response_text[match.end() :]
                )
                stripped_indices.append(source_num)
            else:
                logger.debug(
                    "Citation relevance check PASSED: [Source %d] overlap=%.2f "
                    "claim='%s'",
                    source_num,
                    overlap,
                    claim_text[:80],
                )

        # Clean up whitespace artifacts from removals
        if stripped_indices:
            response_text = re.sub(r"\s+([.,:;!?])", r"\1", response_text)
            response_text = re.sub(r" {2,}", " ", response_text)
            logger.info(
                "Citation relevance check stripped %d citations: sources %s",
                len(stripped_indices),
                sorted(set(stripped_indices)),
            )

        return response_text, stripped_indices

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
        valid_indices = sorted(
            [i for i in found_indices if 1 <= i <= max_valid_sources]
        )
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
                        Citation(
                            url=url, title=title, section=section, source_index=idx
                        )
                    )

        return citations
