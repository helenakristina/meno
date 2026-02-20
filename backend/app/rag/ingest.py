"""RAG document ingestion pipeline.

Handles chunking source documents, generating OpenAI embeddings,
and storing them in the pgvector-enabled rag_documents table in Supabase.

Cost reference: text-embedding-3-small is $0.02 per 1M tokens (~$0.00002 per 1K tokens).
"""
import asyncio
import logging
import re
from datetime import date

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.supabase import get_client

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMENSIONS = 1536
_MAX_BATCH_SIZE = 100
_COST_PER_1K_TOKENS = 0.00002  # text-embedding-3-small pricing


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def chunk_document(
    text: str,
    title: str,
    source_url: str,
    chunk_size: int = 500,
    overlap: int = 50,
    section_name: str | None = None,
) -> list[dict]:
    """Split a document into overlapping chunks for embedding.

    Uses approximate token counting (1 token ≈ 4 chars) with a sliding window
    and tries to break on sentence boundaries to preserve coherent context.

    Args:
        text: Full document text to chunk.
        title: Document title stored as metadata on each chunk.
        source_url: Source URL stored as metadata on each chunk.
        chunk_size: Target chunk size in approximate tokens (default 500).
        overlap: Overlap between adjacent chunks in approximate tokens (default 50).
        section_name: Optional section name within the document.

    Returns:
        List of chunk dicts with keys: content, title, source_url,
        section_name, chunk_index.
    """
    chunk_chars = chunk_size * 4
    overlap_chars = overlap * 4

    # Split into sentences; handles ". ", ".\n", "! ", "? " as terminators
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[dict] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        s_len = len(sentence)

        if current_len + s_len > chunk_chars and current:
            # Emit the current chunk
            chunks.append(
                {
                    "content": " ".join(current),
                    "title": title,
                    "source_url": source_url,
                    "section_name": section_name,
                    "chunk_index": len(chunks),
                }
            )

            # Carry over trailing sentences that fit within the overlap window
            overlap_carry: list[str] = []
            carry_len = 0
            for s in reversed(current):
                if carry_len + len(s) + 1 <= overlap_chars:
                    overlap_carry.insert(0, s)
                    carry_len += len(s) + 1
                else:
                    break

            current = overlap_carry
            current_len = carry_len

        current.append(sentence)
        current_len += s_len + 1  # +1 for the space between sentences

    # Flush any remaining content as the final chunk
    if current:
        chunks.append(
            {
                "content": " ".join(current),
                "title": title,
                "source_url": source_url,
                "section_name": section_name,
                "chunk_index": len(chunks),
            }
        )

    logger.info(
        "Chunked '%s' into %d chunks (size=%d tokens, overlap=%d tokens)",
        title,
        len(chunks),
        chunk_size,
        overlap,
    )
    return chunks


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using text-embedding-3-small.

    Batches requests in groups of up to 100 and retries with exponential backoff
    on transient API failures.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 1536-dimensional embedding vectors, one per input text.

    Cost estimate: $0.00002 per 1K tokens (text-embedding-3-small).
    """
    if not texts:
        return []

    client = _openai_client()
    all_embeddings: list[list[float]] = []
    total_tokens = 0
    total_batches = (len(texts) + _MAX_BATCH_SIZE - 1) // _MAX_BATCH_SIZE

    for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + _MAX_BATCH_SIZE]
        batch_num = batch_start // _MAX_BATCH_SIZE + 1

        logger.info(
            "Embedding batch %d/%d (%d texts)", batch_num, total_batches, len(batch)
        )

        for attempt in range(4):
            try:
                response = await client.embeddings.create(
                    model=_EMBEDDING_MODEL,
                    input=batch,
                )
                break
            except Exception as e:
                if attempt == 3:
                    logger.error("Embedding API failed after 4 attempts: %s", e)
                    raise
                wait = 2**attempt
                logger.warning(
                    "Embedding API error (attempt %d/4), retrying in %ds: %s",
                    attempt + 1,
                    wait,
                    e,
                )
                await asyncio.sleep(wait)

        batch_embeddings = [item.embedding for item in response.data]
        total_tokens += response.usage.total_tokens

        for i, emb in enumerate(batch_embeddings):
            if len(emb) != _EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding {batch_start + i} has {len(emb)} dims, "
                    f"expected {_EMBEDDING_DIMENSIONS}"
                )

        all_embeddings.extend(batch_embeddings)

    estimated_cost = (total_tokens / 1000) * _COST_PER_1K_TOKENS
    logger.info(
        "Generated %d embeddings, total tokens: %d, estimated cost: $%.5f",
        len(all_embeddings),
        total_tokens,
        estimated_cost,
    )
    return all_embeddings


async def store_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    source_type: str,
    publication_date: date | None = None,
) -> None:
    """Insert document chunks with their embeddings into rag_documents.

    Args:
        chunks: Chunk dicts from chunk_document() — each has content, title,
                source_url, section_name, chunk_index.
        embeddings: Parallel list of 1536-dim embedding vectors.
        source_type: Source category, e.g. 'wiki', 'pubmed', 'guidelines'.
        publication_date: Optional publication date for the source document.

    Raises:
        ValueError: If chunks and embeddings lengths do not match.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must have equal length"
        )

    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        # pgvector expects a text literal in the form "[x1,x2,...,xN]"
        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        row: dict = {
            "source_url": chunk["source_url"],
            "title": chunk["title"],
            "source_type": source_type,
            "section_name": chunk.get("section_name"),
            "content": chunk["content"],
            "embedding": vector_str,
        }
        if publication_date is not None:
            row["publication_date"] = publication_date.isoformat()
        rows.append(row)

    client = await get_client()
    try:
        await client.from_("rag_documents").insert(rows).execute()
        logger.info(
            "Stored %d chunks from '%s' (source_type=%s)",
            len(rows),
            chunks[0]["title"] if chunks else "unknown",
            source_type,
        )
    except Exception as e:
        logger.error("Failed to store %d chunks: %s", len(rows), e, exc_info=True)
        raise
