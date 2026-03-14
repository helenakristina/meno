"""POST /api/chat — Ask Meno conversational endpoint with RAG grounding.

Each request is independent (no conversation history sent to OpenAI) to keep
costs low while still storing the full conversation in Supabase for UX continuity.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    CurrentUser,
    get_ask_meno_service,
)
from app.services.ask_meno import AskMenoService
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationMessagesResponse,
)
from app.exceptions import DatabaseError, EntityNotFoundError
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# -------------------------------------------------------------------------------
# Ask Meno
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
    ask_meno_service: AskMenoService = Depends(get_ask_meno_service),
) -> ChatResponse:
    """Handle an Ask Meno question with RAG grounding.

    Raises:
        HTTPException: 400 if the message is empty.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 500 if the LLM or database fails.
    """
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    try:
        return await ask_meno_service.ask(
            user_id=user_id,
            message=message,
            conversation_id=payload.conversation_id,
        )
    except DatabaseError as exc:
        logger.error("Ask Meno failed for user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI assistant is temporarily unavailable. Please try again in a moment.",
        )


@router.get(
    "/suggested-prompts",
    summary="Get personalized starter prompts",
    description=(
        "Get personalized starter prompts based on user's recent symptom logs. "
        "Returns up to 6 prompts: symptom-specific ones from the last 30 days, "
        "filled with general prompts if fewer than 6 symptoms found."
    ),
)
async def get_suggested_prompts(
    user_id: CurrentUser,
    ask_meno_service: AskMenoService = Depends(get_ask_meno_service),
) -> dict:
    """Get personalized starter prompts for Ask Meno.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 500 if database or config load fails.
    """
    try:
        return await ask_meno_service.get_suggested_prompts(user_id=user_id)
    except Exception as exc:
        logger.error(
            "Failed to get suggested prompts for user %s: %s",
            hash_user_id(user_id),
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch personalized prompts",
        )


# -------------------------------------------------------------------------------
# Conversation History
# -------------------------------------------------------------------------------


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List user's conversations",
    description="Retrieve a paginated list of all conversations for the current user, sorted by most recent first.",
)
async def list_conversations(
    user_id: CurrentUser,
    ask_meno_service: AskMenoService = Depends(get_ask_meno_service),
    limit: int = Query(default=20, ge=1, le=100, description="Number of conversations per page"),
    offset: int = Query(default=0, ge=0, description="Number of conversations to skip"),
) -> ConversationListResponse:
    """List all conversations for the current user.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 500 if database query fails.
    """
    try:
        return await ask_meno_service.list_conversations(user_id, limit, offset)
    except DatabaseError as exc:
        logger.error("Failed to list conversations for user %s: %s", hash_user_id(user_id), exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load conversations",
        )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationMessagesResponse,
    summary="Load conversation messages",
    description="Retrieve the full message history of a specific conversation for resuming.",
)
async def get_conversation(
    conversation_id: UUID,
    user_id: CurrentUser,
    ask_meno_service: AskMenoService = Depends(get_ask_meno_service),
) -> ConversationMessagesResponse:
    """Load a specific conversation's messages (for resuming).

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if conversation not found or doesn't belong to user.
        HTTPException: 500 if database query fails.
    """
    try:
        return await ask_meno_service.get_conversation(conversation_id, user_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DatabaseError as exc:
        logger.error("Failed to load conversation %s: %s", conversation_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load conversation",
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    description="Permanently delete a conversation and its message history.",
)
async def delete_conversation(
    conversation_id: UUID,
    user_id: CurrentUser,
    ask_meno_service: AskMenoService = Depends(get_ask_meno_service),
) -> None:
    """Delete a conversation (with ownership verification).

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if conversation not found or doesn't belong to user.
        HTTPException: 500 if database delete fails.
    """
    try:
        await ask_meno_service.delete_conversation(conversation_id, user_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DatabaseError as exc:
        logger.error("Failed to delete conversation %s: %s", conversation_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation",
        )
