"""RAG retrieval for the Ask Meno knowledge base.

Retrieves relevant document chunks by fetching all documents from Supabase and
computing hybrid scores (semantic + keyword) in Python. This avoids pgvector RPC
type-conversion issues with the Supabase Python client / PostgREST layer.

Hybrid search combines semantic similarity (embedding-based) with keyword matching
via Reciprocal Rank Fusion (RRF). This improves retrieval for queries containing
specific medical terms (e.g., "estradiol patch", "vaginal atrophy") where exact
keyword matching complements embedding-based similarity.

The match_rag_documents SQL function (documented below) is no longer used by
Python code but is kept for direct SQL queries and debugging in the Supabase
SQL Editor.

    CREATE OR REPLACE FUNCTION match_rag_documents(
        query_embedding vector(1536),
        match_count int DEFAULT 5
    )
    RETURNS TABLE (
        id uuid,
        content text,
        title text,
        source_url text,
        source_type text,
        similarity float
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT
            rd.id,
            rd.content,
            rd.title,
            rd.source_url,
            rd.source_type,
            1 - (rd.embedding <=> query_embedding) AS similarity
        FROM rag_documents rd
        ORDER BY rd.embedding <=> query_embedding
        LIMIT match_count;
    END;
    $$;
"""

import logging
import math
import re

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.supabase import get_client

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _parse_embedding(raw: object) -> list[float] | None:
    """Normalise the embedding value returned by PostgREST.

    PostgREST may return a vector column as a string '[x1,x2,...]' or as a
    Python list, depending on the supabase-py / postgrest-py version.
    Returns None if the value can't be parsed.
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        try:
            return [float(x) for x in raw.strip("[]").split(",")]
        except ValueError:
            logger.warning("RAG: Could not parse embedding string: %s...", raw[:60])
            return None
    logger.warning("RAG: Unexpected embedding type: %s", type(raw).__name__)
    return None


_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "that", "this", "it", "its",
    "i", "my", "me", "we", "our", "you", "your", "they", "their",
    "what", "how", "when", "where", "which", "who",
})


def _keyword_score(query: str, content: str) -> float:
    """Keyword relevance score: term frequency of query tokens in content.

    Args:
        query: User's natural language question.
        content: Document content to score.

    Returns:
        Score between 0.0 and 1.0+ (no upper bound, but typically < 1.0 for relevance).
        Higher values indicate more keyword matches.
    """
    # Extract query tokens: at least 3 chars, not stopwords
    tokens = [t for t in re.split(r'\W+', query.lower()) if len(t) >= 3 and t not in _STOPWORDS]
    if not tokens:
        return 0.0

    # Count how many times each token appears in content
    content_lower = content.lower()
    matches = sum(content_lower.count(token) for token in tokens)

    # Normalize: matches per query token, damped by content length
    # Longer documents get slightly lower scores to avoid bias toward verbose chunks
    content_words = max(1, len(content_lower.split()))
    return matches / (len(tokens) * math.sqrt(content_words))


def _reciprocal_rank_fusion(
    semantic_ranked: list[dict],
    keyword_ranked: list[dict],
    k: int = 60,
) -> list[dict]:
    """Combine two ranked lists via Reciprocal Rank Fusion (RRF).

    RRF is a standard method for fusing multiple ranking systems without
    requiring score normalization. Documents appearing in both lists rank
    higher than documents in only one list.

    Score = 1/(k + rank_a) + 1/(k + rank_b)

    Args:
        semantic_ranked: List of docs ranked by semantic similarity (descending).
        keyword_ranked: List of docs ranked by keyword score (descending).
        k: Constant (default 60). Higher k dampens the contribution of each list.

    Returns:
        List of all unique documents, ranked by RRF score (descending).
        Each doc dict includes the "hybrid_score" field.
    """
    # Build rank maps: doc_id -> position (0-indexed)
    sem_rank = {doc["id"]: i for i, doc in enumerate(semantic_ranked)}
    kw_rank = {doc["id"]: i for i, doc in enumerate(keyword_ranked)}

    # Collect all unique docs from both lists
    all_docs = {doc["id"]: doc for doc in semantic_ranked + keyword_ranked}

    # For docs not in a list, assign worst rank (length of that list)
    sem_worst = len(semantic_ranked)
    kw_worst = len(keyword_ranked)

    def rrf_score(doc_id: str) -> float:
        """Calculate RRF score for a document."""
        return (
            1.0 / (k + sem_rank.get(doc_id, sem_worst))
            + 1.0 / (k + kw_rank.get(doc_id, kw_worst))
        )

    # Score and sort all documents by RRF score (descending)
    ranked = sorted(all_docs.values(), key=lambda d: rrf_score(d["id"]), reverse=True)

    # Add hybrid_score field to each doc for transparency
    for doc in ranked:
        doc["hybrid_score"] = rrf_score(doc["id"])

    return ranked


async def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Find the most relevant knowledge base chunks for a user query.

    Uses hybrid search (semantic + keyword) via Reciprocal Rank Fusion (RRF).
    Embeds query with OpenAI, fetches all documents, computes semantic similarity
    and keyword scores in Python, combines via RRF, and returns top-k results.

    Args:
        query: User's natural language question.
        top_k: Number of chunks to return (default 5).

    Returns:
        List of dicts with keys: id, content, title, source_url, source_type,
        section_name, similarity (semantic), hybrid_score (combined). Empty list
        if no documents are stored.
    """
    openai = _openai_client()

    logger.info("RAG: Embedding query (model=%s): '%s'", _EMBEDDING_MODEL, query[:100])
    try:
        response = await openai.embeddings.create(model=_EMBEDDING_MODEL, input=query)
    except Exception:
        logger.exception("RAG: OpenAI embedding call failed for query: '%s'", query[:100])
        raise
    query_embedding: list[float] = response.data[0].embedding
    logger.debug("RAG: Embedding generated, dimensions=%d", len(query_embedding))

    # Fetch all documents with their stored embeddings
    logger.info("RAG: Fetching documents from rag_documents table")
    supabase = await get_client()
    try:
        result = await supabase.table("rag_documents").select(
            "id, content, title, source_url, source_type, section_name, embedding"
        ).execute()
    except Exception:
        logger.exception("RAG: Supabase table fetch failed (rag_documents)")
        raise

    docs: list[dict] = result.data or []
    logger.info("RAG: Fetched %d documents from table", len(docs))

    if not docs:
        logger.warning(
            "RAG: rag_documents table is empty — run the ingestion script to add articles."
        )
        return []

    # Compute semantic similarity and keyword scores in Python
    scored: list[dict] = []
    skipped = 0
    for doc in docs:
        doc_embedding = _parse_embedding(doc.get("embedding"))
        if doc_embedding is None:
            skipped += 1
            continue
        similarity = _cosine_similarity(query_embedding, doc_embedding)
        keyword_score = _keyword_score(query, doc["content"])
        scored.append(
            {
                "id": doc["id"],
                "content": doc["content"],
                "title": doc["title"],
                "source_url": doc["source_url"],
                "source_type": doc["source_type"],
                "section_name": doc.get("section_name"),
                "similarity": similarity,
                "keyword_score": keyword_score,
            }
        )

    if skipped:
        logger.warning("RAG: Skipped %d documents with missing/unparseable embeddings", skipped)

    # Rank by semantic similarity
    semantic_ranked = sorted(scored, key=lambda x: x["similarity"], reverse=True)

    # Rank by keyword score
    keyword_ranked = sorted(scored, key=lambda x: x["keyword_score"], reverse=True)

    # Combine via Reciprocal Rank Fusion (hybrid search)
    combined = _reciprocal_rank_fusion(semantic_ranked, keyword_ranked)
    chunks = combined[:top_k]

    if not chunks:
        logger.warning(
            "RAG: Hybrid search yielded 0 chunks for query '%s'", query[:100]
        )
    else:
        logger.info(
            "RAG: Returning %d chunks (top semantic=%.3f, top hybrid=%.3f, first title='%s')",
            len(chunks),
            chunks[0].get("similarity", 0.0),
            chunks[0].get("hybrid_score", 0.0),
            chunks[0].get("title", "untitled"),
        )

    return chunks
