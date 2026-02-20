"""RAG retrieval for the Ask Meno knowledge base.

Retrieves relevant document chunks using pgvector cosine similarity search.

PREREQUISITE — create this SQL function in Supabase (SQL Editor, run once):

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

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.supabase import get_client

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Find the most relevant knowledge base chunks for a user query.

    Embeds the query using the same OpenAI model used at ingestion, then
    performs cosine similarity search via the match_rag_documents pgvector
    function. Returns results sorted by relevance (highest similarity first).

    Args:
        query: User's natural language question.
        top_k: Number of chunks to retrieve (default 5).

    Returns:
        List of dicts with keys: id, content, title, source_url,
        source_type, similarity. Empty list if no documents are stored.
    """
    client = _openai_client()

    logger.info("Embedding retrieval query: '%s'", query[:100])
    response = await client.embeddings.create(
        model=_EMBEDDING_MODEL,
        input=query,
    )
    query_embedding = response.data[0].embedding

    # pgvector RPC expects the vector as a text literal "[x1,x2,...,xN]"
    vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    supabase = await get_client()
    result = await supabase.rpc(
        "match_rag_documents",
        {"query_embedding": vector_str, "match_count": top_k},
    ).execute()

    chunks: list[dict] = result.data or []
    top_similarity = chunks[0]["similarity"] if chunks else 0.0
    logger.info(
        "Retrieved %d chunks for query '%s...' (top similarity: %.3f)",
        len(chunks),
        query[:50],
        top_similarity,
    )
    return chunks
