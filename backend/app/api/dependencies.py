import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from supabase import AsyncClient

from app.core.config import settings
from app.core.supabase import get_client
from app.repositories.user_repository import UserRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.providers_repository import ProvidersRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.services.llm import LLMService
from app.services.llm_base import LLMProvider
from app.services.openai_provider import OpenAIProvider
from app.services.citations import CitationService
from app.services.storage import StorageService
from app.services.chat import ChatService

logger = logging.getLogger(__name__)


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    client: AsyncClient = Depends(get_client),
) -> str:
    """Validate the Bearer JWT and return the authenticated user's UUID.

    Raises:
        HTTPException: 401 if the Authorization header is missing,
            malformed, or the token is invalid or expired.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    try:
        response = await client.auth.get_user(token)
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(response.user.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token validation failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


CurrentUser = Annotated[str, Depends(get_current_user_id)]


def get_user_repo(client: AsyncClient = Depends(get_client)) -> UserRepository:
    """Dependency for UserRepository.

    Args:
        client: Supabase AsyncClient.

    Returns:
        UserRepository instance for data access.
    """
    return UserRepository(client=client)


def get_symptoms_repo(client: AsyncClient = Depends(get_client)) -> SymptomsRepository:
    """Dependency for SymptomsRepository.

    Args:
        client: Supabase AsyncClient.

    Returns:
        SymptomsRepository instance for data access.
    """
    return SymptomsRepository(client=client)


def get_conversation_repo(client: AsyncClient = Depends(get_client)) -> ConversationRepository:
    """Dependency for ConversationRepository.

    Args:
        client: Supabase AsyncClient.

    Returns:
        ConversationRepository instance for data access.
    """
    return ConversationRepository(client=client)


def get_providers_repo(client: AsyncClient = Depends(get_client)) -> ProvidersRepository:
    """Dependency for ProvidersRepository.

    Args:
        client: Supabase AsyncClient.

    Returns:
        ProvidersRepository instance for data access.
    """
    return ProvidersRepository(client=client)


def get_appointment_repo(client: AsyncClient = Depends(get_client)) -> AppointmentRepository:
    """Dependency for AppointmentRepository.

    Args:
        client: Supabase AsyncClient.

    Returns:
        AppointmentRepository instance for data access.
    """
    return AppointmentRepository(client=client)


def get_llm_service() -> LLMService:
    """Dependency for LLMService.

    Creates an LLMService with the configured provider (OpenAI, Anthropic, etc.).
    The provider is selected via the LLM_PROVIDER environment variable.

    Currently supports:
    - "openai": Uses OpenAI API (gpt-4o-mini for development)
    - "anthropic": Uses Anthropic API (claude-sonnet-4 for production)

    Returns:
        LLMService instance with the configured provider.

    Raises:
        ValueError: If LLM_PROVIDER is set to an unsupported value.
    """
    provider: LLMProvider
    if settings.LLM_PROVIDER == "openai":
        provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    elif settings.LLM_PROVIDER == "anthropic":
        # Future: import AnthropicProvider when implemented
        # provider = AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        raise ValueError(
            f"LLM_PROVIDER=anthropic not yet implemented. "
            "Use LLM_PROVIDER=openai or wait for Anthropic provider."
        )
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}. "
            "Supported values: openai, anthropic"
        )

    logger.info("LLMService initialized with provider: %s", settings.LLM_PROVIDER)
    return LLMService(provider=provider)


def get_citation_service() -> CitationService:
    """Dependency for CitationService.

    Returns:
        CitationService instance for citation extraction and sanitization.
    """
    return CitationService()


def get_storage_service(client: AsyncClient = Depends(get_client)) -> StorageService:
    """Dependency for StorageService.

    Args:
        client: Supabase AsyncClient.

    Returns:
        StorageService instance for file uploads.
    """
    return StorageService(client=client)


def get_chat_service(symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo)) -> ChatService:
    """Dependency for ChatService.

    Args:
        symptoms_repo: SymptomsRepository for accessing symptom logs.

    Returns:
        ChatService instance for chat features (prompts, etc.).
    """
    return ChatService(symptoms_repo=symptoms_repo)
