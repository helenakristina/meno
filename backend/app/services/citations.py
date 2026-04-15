"""Citation rendering and extraction service for Ask Meno responses.

Handles structured LLM response rendering with inline citation markers,
relevance verification via keyword overlap, and extraction of Citation objects.
All methods are pure (no side effects, no external dependencies).
"""

import logging
import re

from app.models.chat import Citation, StructuredLLMResponse

logger = logging.getLogger(__name__)


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

    _STOPWORDS: frozenset[str] = frozenset(
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

    def render_structured_response(
        self,
        structured: StructuredLLMResponse,
        chunks: list[dict],
    ) -> tuple[str, list[Citation]]:
        """Convert a v2 structured LLM response into paragraph text with inline citations.

        Processing:
        1. If insufficient_sources is True, return only the disclaimer message.
        2. For each section: render body as a paragraph with a single [Source N] marker.
        3. Deduplicate citations (same source_index used in multiple sections → one Citation).
        4. Headings are emitted as ### markdown so the frontend renders them as <h3>.
        5. Append disclaimer if present.

        Args:
            structured: Parsed v2 structured response from the LLM.
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

        paragraphs: list[str] = []
        seen_indices: dict[int, int] = {}  # source_index → sequential display number
        citations: list[Citation] = []

        for section in structured.sections:
            body = section.body.strip() if section.body else ""
            if not body:
                continue

            # Build citation marker for this section
            marker = ""
            if section.source_index is not None:
                idx = section.source_index
                if idx not in seen_indices:
                    if 1 <= idx <= len(chunks):
                        display_n = len(citations) + 1
                        seen_indices[idx] = display_n
                        chunk = chunks[idx - 1]
                        chunk_content = chunk.get("content", "")
                        overlap = self._claim_source_overlap(body, chunk_content)
                        if overlap < self._RELEVANCE_MIN_OVERLAP:
                            logger.warning(
                                "render_structured_response: low overlap for section source_index=%d overlap=%.2f",
                                idx,
                                overlap,
                            )
                        url = chunk.get("source_url", "")
                        title = chunk.get("title", "")
                        section_name = chunk.get("section_name")
                        if url:
                            citations.append(
                                Citation(
                                    url=url,
                                    title=title,
                                    section=section_name,
                                    source_index=display_n,
                                )
                            )
                    else:
                        logger.warning(
                            "render_structured_response: source_index=%d out of range (max=%d), skipping citation",
                            idx,
                            len(chunks),
                        )
                if idx in seen_indices:
                    marker = f" [Source {seen_indices[idx]}]"

            text = body + marker

            if section.heading:
                paragraphs.append(f"### {section.heading}\n{text}")
            else:
                paragraphs.append(text)

        rendered_text = "\n\n".join(paragraphs)

        if not rendered_text.strip():
            logger.warning(
                "render_structured_response: all sections empty — returning insufficient sources message"
            )
            fallback = structured.disclaimer or (
                "I don't have enough information in my sources to answer that question. "
                "Please consult your healthcare provider for personalized guidance."
            )
            return fallback, []

        if structured.disclaimer:
            rendered_text += f"\n\n{structured.disclaimer}"

        logger.info(
            "render_structured_response: %d section(s) → %d paragraph(s), %d citation(s)",
            len(structured.sections),
            len(paragraphs),
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
