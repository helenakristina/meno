"""POST /api/chat — Ask Meno conversational endpoint with RAG grounding.

Each request is independent (no conversation history sent to OpenAI) to keep
costs low while still storing the full conversation in Supabase for UX continuity.
"""

import logging
import re
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from supabase import AsyncClient

from app.api.dependencies import CurrentUser
from app.core.config import settings
from app.core.supabase import get_client
from app.llm.system_prompts import LAYER_1, LAYER_2, LAYER_3
from app.models.chat import ChatMessage, ChatRequest, ChatResponse, Citation
from app.rag.retrieval import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

SupabaseClient = Annotated[AsyncClient, Depends(get_client)]



def _build_system_prompt(
    journey_stage: str,
    age: int | None,
    symptom_summary: str,
    chunks: list[dict],
) -> str:
    """Assemble the four-layer system prompt with dynamic user context and RAG sources."""
    age_str = str(age) if age is not None else "unknown"

    source_lines = []
    for i, chunk in enumerate(chunks, start=1):
        url = chunk.get("source_url", "")
        title = chunk.get("title", "").strip()
        content = chunk.get("content", "").strip()
        source_lines.append(f"(Source {i}) {title}\nURL: {url}\nContent: {content}")
    source_count = len(chunks)
    sources_block = (
        "\n\n".join(source_lines) if source_lines else "No source documents available."
    )

    layer_4 = (
        f"User context:\n"
        f"- Journey stage: {journey_stage}\n"
        f"- Age: {age_str}\n"
        f"- Recent symptom summary: {symptom_summary}\n\n"
        f"Source documents — there are exactly {source_count} source(s). "
        f"Only cite [Source 1] through [Source {source_count}]:\n\n{sources_block}"
    )

    return "\n\n".join([LAYER_1, LAYER_2, LAYER_3, layer_4])


def _sanitize_and_renumber_citations(
    response_text: str, max_valid_sources: int
) -> tuple[str, list[int]]:
    """Remove invalid citations and renumber valid ones to match extracted citations.

    Process:
    1. Identify all citations in the text (both [Source N] and [N] formats)
    2. Remove citations that reference sources beyond max_valid_sources (phantom citations)
    3. Renumber remaining citations to 1, 2, 3... to match the extraction order

    Args:
        response_text: Raw response from LLM
        max_valid_sources: Number of unique chunks that were shown in the prompt (post-dedup)

    Returns:
        (cleaned_text, removed_indices)
    """
    removed_indices: list[int] = []
    cleaned_text = response_text

    # First, find all citation indices that actually appear in the text
    found_indices: set[int] = set()
    for match in re.finditer(r"\[Source (\d+)\]", cleaned_text):
        found_indices.add(int(match.group(1)))
    for match in re.finditer(r"(?<![\/\w])\[(\d+)\](?![\w])", cleaned_text):
        start = match.start()
        if start == 0 or cleaned_text[start - 1] in (" ", ".", ":", ";", ",", ")", "—"):
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
            pattern = f"[{old_idx}]"
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

    return cleaned_text, removed_indices


def _extract_citations(response_text: str, chunks: list[dict]) -> list[Citation]:
    """Map [Source N] or [N] references in the response to Citation objects with section context.

    Parses [Source 1], [Source 2], etc. OR [1], [2], etc. and maps them to the corresponding
    chunk's source_url and title. Includes section_name if available in chunk metadata.
    References beyond the available chunks are silently ignored.

    Groups chunks by URL and adds source_index to distinguish multiple chunks from
    the same URL with different sections.
    """
    # Build a map of URL -> list of chunks with that URL (preserving order)
    url_to_chunks: dict[str, list[tuple[int, dict]]] = {}
    for chunk_idx, chunk in enumerate(chunks):
        url = chunk.get("source_url", "")
        if url:
            if url not in url_to_chunks:
                url_to_chunks[url] = []
            url_to_chunks[url].append((chunk_idx, chunk))

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
    seen_urls: set[str] = set()

    for idx in sorted(found_indices):
        chunk_index = idx - 1  # Source N is 1-indexed
        if 0 <= chunk_index < len(chunks):
            chunk = chunks[chunk_index]
            url = chunk.get("source_url", "")
            title = chunk.get("title", "")
            section = chunk.get("section_name")  # May be None

            if url and url not in seen_urls:
                # Determine if we need to add source_index for disambiguation
                source_index = None
                if url in url_to_chunks and len(url_to_chunks[url]) > 1:
                    # Multiple chunks from same URL — use source_index to distinguish
                    source_index = idx  # Use the [Source N] number for clarity

                citations.append(
                    Citation(
                        url=url, title=title, section=section, source_index=source_index
                    )
                )
                seen_urls.add(url)

    return citations


def _calculate_age(date_of_birth: date) -> int:
    today = date.today()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


# -------------------------------------------------------------------------------
# Supabase helpers
# -------------------------------------------------------------------------------


async def _fetch_user_context(
    user_id: str, client: AsyncClient
) -> tuple[str, int | None]:
    """Return (journey_stage, age) for the user. Falls back gracefully if missing."""
    try:
        response = (
            await client.table("users")
            .select("journey_stage, date_of_birth")
            .eq("id", user_id)
            .execute()
        )
        if response.data:
            row = response.data[0]
            journey_stage = row.get("journey_stage") or "unsure"
            dob_raw = row.get("date_of_birth")
            if dob_raw:
                dob = date.fromisoformat(dob_raw)
                age = _calculate_age(dob)
            else:
                age = None
            return journey_stage, age
    except Exception as exc:
        logger.warning("Failed to fetch user context for %s: %s", user_id, exc)
    return "unsure", None


async def _fetch_symptom_summary(user_id: str, client: AsyncClient) -> str:
    """Return the latest cached symptom summary text, or a default message."""
    try:
        response = (
            await client.table("symptom_summary_cache")
            .select("summary_text")
            .eq("user_id", user_id)
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0].get("summary_text") or "No symptom data logged yet."
    except Exception as exc:
        logger.warning("Failed to fetch symptom summary for %s: %s", user_id, exc)
    return "No symptom data logged yet."


async def _load_conversation(
    conversation_id: UUID, user_id: str, client: AsyncClient
) -> list[dict]:
    """Fetch the messages array from an existing conversation.

    Raises HTTPException 404 if the conversation doesn't exist or doesn't
    belong to this user.
    """
    try:
        response = (
            await client.table("conversations")
            .select("messages")
            .eq("id", str(conversation_id))
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB query failed loading conversation %s for user %s: %s",
            conversation_id,
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load conversation",
        )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return response.data[0].get("messages") or []


async def _save_conversation(
    conversation_id: UUID | None,
    user_id: str,
    messages: list[dict],
    client: AsyncClient,
) -> UUID:
    """Upsert conversation messages. Returns the (possibly new) conversation UUID."""
    if conversation_id is not None:
        try:
            await (
                client.table("conversations")
                .update({"messages": messages})
                .eq("id", str(conversation_id))
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed for conversation %s: %s",
                conversation_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save conversation",
            )
        return conversation_id

    # New conversation
    try:
        response = (
            await client.table("conversations")
            .insert({"user_id": user_id, "messages": messages})
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB insert failed creating conversation for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save conversation",
        )

    if not response.data:
        logger.error(
            "Supabase returned no data after conversation insert for user %s", user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save conversation",
        )

    return UUID(response.data[0]["id"])


# -------------------------------------------------------------------------------
# OpenAI call
# -------------------------------------------------------------------------------


async def _call_openai(system_prompt: str, user_message: str) -> tuple[str, int, int]:
    """Call gpt-4o-mini and return (response_text, prompt_tokens, completion_tokens)."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.5,  # Lowered for better determinism while maintaining quality
        max_tokens=800,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    text = response.choices[0].message.content or ""
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    return text, prompt_tokens, completion_tokens


# -------------------------------------------------------------------------------
# Endpoint
# -------------------------------------------------------------------------------


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask Meno a question",
    description=(
        "Submit a question to the Ask Meno AI. Returns an evidence-based response "
        "grounded in curated sources, with inline citations. Each message is processed "
        "independently (conversation history is stored but not re-sent to OpenAI)."
    ),
)
async def ask_meno(
    payload: ChatRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> ChatResponse:
    """Handle an Ask Meno question with RAG grounding.

    Raises:
        HTTPException: 400 if the message is empty.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 404 if a provided conversation_id doesn't exist or belong to the user.
        HTTPException: 500 if OpenAI or the database fails.
    """
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    # Gather context in parallel where possible
    journey_stage, age = await _fetch_user_context(user_id, client)
    symptom_summary = await _fetch_symptom_summary(user_id, client)

    # Load existing conversation messages (for storage continuity — not sent to OpenAI)
    existing_messages: list[dict] = []
    if payload.conversation_id is not None:
        existing_messages = await _load_conversation(
            payload.conversation_id, user_id, client
        )

    # RAG retrieval
    logger.info(
        "RAG: Starting retrieval for user=%s query='%s'", user_id, message[:100]
    )
    try:
        chunks = await retrieve_relevant_chunks(message, top_k=5)
        if chunks:
            logger.info(
                "RAG: Success — %d chunks retrieved for user=%s", len(chunks), user_id
            )
        else:
            logger.warning(
                "RAG: Empty result for user=%s query='%s' — response will have no source grounding",
                user_id,
                message[:100],
            )
    except Exception as exc:
        logger.error(
            "RAG: Retrieval raised an exception for user=%s query='%s': %s",
            user_id,
            message[:100],
            exc,
            exc_info=True,
        )
        chunks = []  # Degrade gracefully — answer without sources

    # Deduplicate chunks by URL before building the prompt.
    # Keep only the first occurrence of each unique URL.
    seen_urls: set[str] = set()
    unique_chunks: list[dict] = []

    for chunk in chunks:
        url = chunk.get("source_url", "")
        if url not in seen_urls:
            unique_chunks.append(chunk)
            seen_urls.add(url)

    if len(chunks) != len(unique_chunks):
        logger.info(
            "RAG: Deduplicated %d chunks → %d unique URLs",
            len(chunks),
            len(unique_chunks),
        )
    chunks = unique_chunks

    # Build system prompt
    system_prompt = _build_system_prompt(journey_stage, age, symptom_summary, chunks)

    # Call OpenAI
    try:
        response_text, prompt_tokens, completion_tokens = await _call_openai(
            system_prompt, message
        )
    except Exception as exc:
        logger.error("OpenAI call failed for user %s: %s", user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The AI assistant is temporarily unavailable. "
                "Please try again in a moment."
            ),
        )

    logger.info(
        "OpenAI chat completed: user=%s prompt_tokens=%d completion_tokens=%d chunks=%d",
        user_id,
        prompt_tokens,
        completion_tokens,
        len(chunks),
    )

    # Sanitize phantom citations and renumber valid ones
    logger.debug("Before sanitization, response contains: %s", response_text[:200])
    response_text, _ = _sanitize_and_renumber_citations(response_text, len(chunks))
    logger.debug("After sanitization, response contains: %s", response_text[:200])

    # Extract citations with section context
    citations = _extract_citations(response_text, chunks)
    logger.info("Extracted %d valid citations from response", len(citations))

    # Build updated messages list for storage
    user_msg = ChatMessage(role="user", content=message)
    assistant_msg = ChatMessage(
        role="assistant", content=response_text, citations=citations
    )
    updated_messages = existing_messages + [
        user_msg.model_dump(),
        assistant_msg.model_dump(),
    ]

    # Persist conversation
    conversation_id = await _save_conversation(
        payload.conversation_id, user_id, updated_messages, client
    )

    # Log all citation patterns found in the response for debugging
    all_citations = re.findall(r"\[Source (\d+)\]|\[(\d+)\]", response_text)
    citation_nums = [int(m[0] or m[1]) for m in all_citations]
    logger.info(
        "Returning response: %d extracted citations, %d citation patterns in text: %s",
        len(citations),
        len(citation_nums),
        sorted(set(citation_nums)) if citation_nums else "none",
    )

    return ChatResponse(
        message=response_text,
        citations=citations,
        conversation_id=conversation_id,
    )
