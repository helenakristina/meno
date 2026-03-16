"""Citation extraction and sanitization service for Ask Meno responses.

Handles phantom citation removal, renumbering, relevance verification, and
extraction of Citation objects from LLM responses. All functions are pure
(no side effects, no external dependencies).
"""

import logging
import re
from typing import NamedTuple

from app.models.chat import Citation, StructuredLLMResponse

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

    # Phrases that are safe to include without a source citation (generic advice)
    _SAFE_UNSOURCED_PATTERNS: tuple[str, ...] = (
        "consult your healthcare provider",
        "consult a healthcare provider",
        "talk to your doctor",
        "talk to your healthcare provider",
        "talk with your",
        "speak with your",
        "speak to your",
        "discuss with your",
        "seek medical",
        "ask your provider",
        "ask your doctor",
        "track your symptoms",
    )

    def render_structured_response(
        self,
        structured: StructuredLLMResponse,
        chunks: list[dict],
    ) -> tuple[str, list[Citation]]:
        """Convert a structured LLM response into rendered text with inline citations.

        Processing:
        1. If insufficient_sources is True, return only the disclaimer message.
        2. For each claim: strip if unsourced (source_indices empty) unless the claim
           matches a safe generic-advice pattern.
        3. For sourced claims: verify each citation via keyword overlap; strip indices
           that fail the relevance check.
        4. Render sections into human-readable text with [Source N] markers.
        5. If every claim was stripped, return the insufficient-sources message.

        Args:
            structured: Parsed structured response from the LLM.
            chunks: RAG chunks passed to the LLM (0-indexed internally; sources are 1-indexed).

        Returns:
            Tuple of (rendered_text, citations_list).
        """
        if structured.insufficient_sources:
            message = structured.disclaimer or (
                "I don't have enough information in my sources to answer that question. "
                "Please consult your healthcare provider for personalized guidance."
            )
            return message, []

        used_source_indices: set[int] = set()
        rendered_parts: list[str] = []

        for section in structured.sections:
            section_parts: list[str] = []

            if section.heading:
                section_parts.append(f"**{section.heading}**")

            for claim in section.claims:
                # ---------------------------------------------------------
                # Fix 1: Strip inline citation markers the LLM may have
                # embedded in the text field itself (e.g. "CBD may help [3]").
                # We manage citation markers from source_indices only.
                # ---------------------------------------------------------
                clean_text = re.sub(r"\s*\[Source\s+\d+\]", "", claim.text)
                clean_text = re.sub(r"\s*\[(\d+)\]", "", clean_text)
                clean_text = clean_text.strip()

                if not clean_text:
                    logger.debug("Claim empty after stripping inline markers, skipping")
                    continue

                # Log what the LLM returned vs what we cleaned
                if clean_text != claim.text.strip():
                    logger.info(
                        "Stripped inline citation markers from claim text: "
                        "original='%s' cleaned='%s'",
                        claim.text[:120],
                        clean_text[:120],
                    )

                # Filter to valid 1-based indices within the chunks range
                valid_indices = [
                    idx for idx in claim.source_indices if 1 <= idx <= len(chunks)
                ]

                # Log invalid indices so we can track phantom citations
                invalid_indices = [
                    idx for idx in claim.source_indices if idx < 1 or idx > len(chunks)
                ]
                if invalid_indices:
                    logger.warning(
                        "Claim has out-of-range source_indices %s (max=%d): '%s'",
                        invalid_indices,
                        len(chunks),
                        clean_text[:80],
                    )

                if not valid_indices:
                    # Unsourced claim: keep only if it's safe generic advice
                    claim_lower = clean_text.lower()
                    if any(pat in claim_lower for pat in self._SAFE_UNSOURCED_PATTERNS):
                        section_parts.append(clean_text)
                        logger.debug(
                            "Keeping unsourced safe claim: %s", clean_text[:80]
                        )
                    else:
                        logger.info(
                            "Stripping unsourced claim: '%s' (original source_indices=%s)",
                            clean_text[:80],
                            claim.source_indices,
                        )
                    continue

                # Verify each citation via keyword overlap
                verified_indices: list[int] = []
                for idx in valid_indices:
                    chunk_content = chunks[idx - 1].get("content", "")
                    overlap = self._claim_source_overlap(clean_text, chunk_content)
                    if overlap >= self._RELEVANCE_MIN_OVERLAP:
                        verified_indices.append(idx)
                        used_source_indices.add(idx)
                        logger.debug(
                            "Citation relevance PASSED: source=%d overlap=%.2f claim='%s'",
                            idx,
                            overlap,
                            clean_text[:80],
                        )
                    else:
                        logger.warning(
                            "Citation relevance check FAILED: source=%d overlap=%.2f "
                            "(threshold=%.2f) claim='%s' source_title='%s'",
                            idx,
                            overlap,
                            self._RELEVANCE_MIN_OVERLAP,
                            clean_text[:120],
                            chunks[idx - 1].get("title", "untitled")[:60],
                        )

                if verified_indices:
                    markers = "".join(f" [Source {i}]" for i in verified_indices)
                    section_parts.append(f"{clean_text}{markers}")
                else:
                    # All citations failed — keep only if safe generic advice
                    claim_lower = clean_text.lower()
                    if any(pat in claim_lower for pat in self._SAFE_UNSOURCED_PATTERNS):
                        section_parts.append(clean_text)
                    else:
                        logger.info(
                            "Stripping claim — all citations failed relevance: '%s'",
                            clean_text[:80],
                        )

            if section_parts:
                if section.heading:
                    # Heading on first line, each claim as its own bullet below
                    heading_line = section_parts[0]
                    bullet_lines = "\n".join(f"- {c}" for c in section_parts[1:])
                    rendered_parts.append(
                        f"{heading_line}\n{bullet_lines}"
                        if bullet_lines
                        else heading_line
                    )
                else:
                    # No heading — each claim as its own bullet
                    rendered_parts.append("\n".join(f"- {c}" for c in section_parts))

        if structured.disclaimer:
            rendered_parts.append(structured.disclaimer)

        if not rendered_parts:
            logger.warning(
                "render_structured_response: all claims stripped — returning insufficient sources message"
            )
            return (
                "I don't have enough information in my sources to answer that question. "
                "Please consult your healthcare provider for personalized guidance.",
                [],
            )

        rendered_text = "\n\n".join(rendered_parts)

        # Build sequential citation list and renumber markers in the text.
        # The LLM may use non-contiguous source indices (e.g. 1 and 3 when
        # source 2 was unused). The frontend displays citations as a numbered
        # list, so marker [3] in the text must become [2] if it's the second
        # citation in the list.
        sorted_indices = sorted(used_source_indices)
        # Map: original source index → sequential display index (1-based)
        renumber_map: dict[int, int] = {
            old_idx: new_idx for new_idx, old_idx in enumerate(sorted_indices, start=1)
        }

        # Apply renumbering to rendered text (process in reverse to avoid
        # replacing [Source 1] inside [Source 11], etc.)
        for old_idx in sorted(renumber_map.keys(), reverse=True):
            new_idx = renumber_map[old_idx]
            if old_idx != new_idx:
                rendered_text = rendered_text.replace(
                    f"[Source {old_idx}]", f"[Source {new_idx}]"
                )

        if any(v != k for k, v in renumber_map.items()):
            logger.info(
                "Renumbered citation markers in rendered text: %s",
                {k: v for k, v in renumber_map.items() if k != v},
            )

        citations: list[Citation] = []
        for display_idx, source_idx in enumerate(sorted_indices, start=1):
            chunk = chunks[source_idx - 1]
            url = chunk.get("source_url", "")
            title = chunk.get("title", "")
            section_name = chunk.get("section_name")
            if url:
                citations.append(
                    Citation(
                        url=url,
                        title=title,
                        section=section_name,
                        source_index=display_idx,
                    )
                )

        logger.info(
            "render_structured_response: %d section(s) → %d text part(s), %d citation(s)",
            len(structured.sections),
            len(rendered_parts),
            len(citations),
        )

        return rendered_text, citations

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
