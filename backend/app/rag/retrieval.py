"""RAG retrieval for the Ask Meno knowledge base.

Retrieves relevant document chunks using pgvector semantic search via the
match_rag_documents Supabase RPC function. The function accepts the query
embedding as text (to avoid PostgREST vector type-conversion issues) and
casts to vector internally.

    CREATE OR REPLACE FUNCTION match_rag_documents(
        query_embedding text,
        match_count int DEFAULT 5
    )
    RETURNS TABLE (
        id uuid,
        content text,
        title text,
        source_url text,
        source_type text,
        section_name text,
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
            rd.section_name,
            1 - (rd.embedding <=> query_embedding::vector) AS similarity
        FROM rag_documents rd
        ORDER BY rd.embedding <=> query_embedding::vector
        LIMIT match_count;
    END;
    $$;
"""

import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.supabase import get_client

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"

# ---------------------------------------------------------------------------
# Relevance threshold: chunks with semantic similarity below this value are
# excluded from results, even if they rank in the top-k. This prevents
# marginally related documents from being sent to the LLM, which reduces
# the risk of the LLM mis-citing a source that covers a related but
# different topic.
#
# Tuning guidance:
#   - Log similarity scores for a week and review misattributed citations.
#   - Good matches typically score 0.35+; marginal matches fall 0.20-0.35.
#   - Start conservative (0.25) and raise toward 0.30-0.35 as you collect data.
#   - Setting this too high will result in many queries returning no sources,
#     which triggers the "I don't have enough information" fallback.
# ---------------------------------------------------------------------------
_MIN_SIMILARITY = 0.25


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _normalize_query(query: str) -> str:
    """Normalize query text before embedding to improve retrieval.

    Strips hyphens, extra whitespace, and other characters that cause
    the embedding model to produce unexpected vectors.
    """
    normalized = query.replace("-", " ")
    normalized = " ".join(normalized.split())  # collapse multiple spaces
    return normalized


async def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
    min_similarity: float = _MIN_SIMILARITY,
) -> list[dict]:
    """Find the most relevant knowledge base chunks for a user query.

    Embeds the query with OpenAI, then calls the match_rag_documents pgvector
    function via Supabase RPC to find the top-k most similar chunks.

    Chunks with a semantic similarity below min_similarity are excluded to
    prevent marginally related documents from being cited by the LLM.

    Args:
        query: User's natural language question.
        top_k: Maximum number of chunks to return (default 5).
        min_similarity: Minimum cosine similarity to include a chunk (default 0.25).

    Returns:
        List of dicts with keys: id, content, title, source_url, source_type,
        section_name, similarity. Empty list if no documents meet the relevance
        threshold.
    """
    openai = _openai_client()
    query = _normalize_query(query)

    logger.info("RAG: Embedding query (model=%s): '%s'", _EMBEDDING_MODEL, query[:100])
    try:
        response = await openai.embeddings.create(model=_EMBEDDING_MODEL, input=query)
    except Exception:
        logger.exception(
            "RAG: OpenAI embedding call failed for query: '%s'", query[:100]
        )
        raise
    query_embedding: list[float] = response.data[0].embedding
    logger.debug("RAG: Embedding generated, dimensions=%d", len(query_embedding))

    # Call pgvector similarity search via Supabase RPC
    # The function accepts text and casts to vector internally to avoid
    # PostgREST type-conversion issues with the vector type.
    logger.info("RAG: Calling match_rag_documents RPC (top_k=%d)", top_k)
    supabase = await get_client()
    try:
        result = await supabase.rpc(
            "match_rag_documents",
            {
                "query_embedding": str(query_embedding),
                "match_count": top_k,
            },
        ).execute()
    except Exception:
        logger.exception("RAG: Supabase RPC match_rag_documents failed")
        raise

    chunks: list[dict] = result.data or []
    logger.info("RAG: RPC returned %d chunks", len(chunks))

    if not chunks:
        logger.warning(
            "RAG: No chunks returned from pgvector for query '%s'",
            query[:100],
        )
        return []

    # Diagnostic logging for all candidates before filtering
    for i, c in enumerate(chunks):
        logger.info(
            "RAG candidate #%d: title='%s' similarity=%.4f",
            i + 1,
            c.get("title", "untitled")[:80],
            c.get("similarity", 0.0),
        )

    # Filter by minimum semantic similarity
    before_count = len(chunks)
    chunks = [c for c in chunks if c.get("similarity", 0.0) >= min_similarity]

    filtered_out = before_count - len(chunks)
    if filtered_out > 0:
        logger.info(
            "RAG: Filtered out %d chunks below similarity threshold %.3f",
            filtered_out,
            min_similarity,
        )

    if not chunks:
        logger.warning(
            "RAG: No chunks met similarity threshold %.3f for query '%s'",
            min_similarity,
            query[:100],
        )
    else:
        logger.info(
            "RAG: Returning %d chunks (top similarity=%.3f, first title='%s')",
            len(chunks),
            chunks[0].get("similarity", 0.0),
            chunks[0].get("title", "untitled"),
        )

    return chunks
