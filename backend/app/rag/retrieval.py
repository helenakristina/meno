"""RAG retrieval for the Ask Meno knowledge base.

Retrieves relevant document chunks by fetching all documents from Supabase and
computing cosine similarity in Python. This avoids pgvector RPC type-conversion
issues with the Supabase Python client / PostgREST layer.

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


async def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Find the most relevant knowledge base chunks for a user query.

    Embeds the query with OpenAI, fetches all stored documents, computes
    cosine similarity in Python, and returns the top-k results sorted by
    relevance. This approach bypasses pgvector RPC type-conversion issues
    with the Supabase Python / PostgREST client.

    Args:
        query: User's natural language question.
        top_k: Number of chunks to return (default 5).

    Returns:
        List of dicts with keys: id, content, title, source_url,
        source_type, similarity. Empty list if no documents are stored.
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
            "id, content, title, source_url, source_type, embedding"
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

    # Compute cosine similarity in Python
    scored: list[dict] = []
    skipped = 0
    for doc in docs:
        doc_embedding = _parse_embedding(doc.get("embedding"))
        if doc_embedding is None:
            skipped += 1
            continue
        similarity = _cosine_similarity(query_embedding, doc_embedding)
        scored.append(
            {
                "id": doc["id"],
                "content": doc["content"],
                "title": doc["title"],
                "source_url": doc["source_url"],
                "source_type": doc["source_type"],
                "similarity": similarity,
            }
        )

    if skipped:
        logger.warning("RAG: Skipped %d documents with missing/unparseable embeddings", skipped)

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    chunks = scored[:top_k]

    if not chunks:
        logger.warning(
            "RAG: Similarity search yielded 0 chunks for query '%s'", query[:100]
        )
    else:
        logger.info(
            "RAG: Returning %d chunks (top similarity=%.3f, first title='%s')",
            len(chunks),
            chunks[0]["similarity"],
            chunks[0].get("title", "untitled"),
        )

    return chunks
