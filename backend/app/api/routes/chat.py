"""POST /api/chat — Ask Meno conversational endpoint with RAG grounding.

Each request is independent (no conversation history sent to OpenAI) to keep
costs low while still storing the full conversation in Supabase for UX continuity.
"""

import logging
import re
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID


from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from supabase import AsyncClient

from app.api.dependencies import (
    CurrentUser,
    get_user_repo,
    get_symptoms_repo,
    get_conversation_repo,
    get_citation_service,
)
from app.core.config import settings
from app.core.supabase import get_client
from app.repositories.user_repository import UserRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services.citations import CitationService
from app.llm.system_prompts import LAYER_1, LAYER_2, LAYER_3
from app.models.chat import ChatMessage, ChatRequest, ChatResponse
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
    user_repo: UserRepository = Depends(get_user_repo),
    symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    citation_service: CitationService = Depends(get_citation_service),
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
    journey_stage, age = await user_repo.get_context(user_id)
    symptom_summary = await symptoms_repo.get_summary(user_id)

    # Load existing conversation messages (for storage continuity — not sent to OpenAI)
    existing_messages: list[dict] = []
    if payload.conversation_id is not None:
        existing_messages = await conversation_repo.load(
            payload.conversation_id, user_id
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

    seen_url_sections: set[tuple[str, str]] = set()
    unique_chunks: list[dict] = []

    for chunk in chunks:
        url = chunk.get("source_url", "")
        section = chunk.get("section_name", "") or "default"

        # Strip fragment to get base URL
        base_url = urlparse(url)._replace(fragment="").geturl()

        key = (base_url, section)
        if key not in seen_url_sections:
            unique_chunks.append(chunk)
            seen_url_sections.add(key)

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
    sanitize_result = citation_service.sanitize_and_renumber(response_text, len(chunks))
    response_text = sanitize_result.text
    logger.debug("After sanitization, response contains: %s", response_text[:200])

    # Extract citations with section context
    citations = citation_service.extract(response_text, chunks)
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
    conversation_id = await conversation_repo.save(
        payload.conversation_id, user_id, updated_messages
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
