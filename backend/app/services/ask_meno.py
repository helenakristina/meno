"""AskMenoService — orchestrates all Ask Meno conversational AI features.

Handles the full Ask Meno flow:
- ask(): RAG retrieval, prompt assembly, LLM call, citation extraction, conversation persistence
- get_suggested_prompts(): Personalized starter prompts from recent symptom logs
- list_conversations(): Paginated conversation history
- get_conversation(): Load a specific conversation for resuming
- delete_conversation(): Delete a conversation permanently

The route becomes a thin wrapper that calls service methods and handles HTTP concerns.
"""

import asyncio
import json
import logging
import random
import re
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import ValidationError

from app.exceptions import DatabaseError
from app.models.chat import (
    ChatMessage,
    ChatResponse,
    Citation,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationSummary,
    StructuredClaim,
    StructuredLLMResponse,
    StructuredSection,
    SuggestedPromptsResponse,
)
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.repositories.user_repository import UserRepository
from app.services.citations import CitationService
from app.services.llm import LLMService
from app.services.prompts import PromptService
from app.utils.conversations import build_conversation_title
from app.utils.dates import get_date_range
from app.utils.logging import hash_user_id, safe_len, safe_summary

logger = logging.getLogger(__name__)


class AskMenoService:
    """Orchestrates all Ask Meno conversational AI features.

    Raises domain exceptions (DatabaseError, EntityNotFoundError) that routes
    convert to HTTP responses.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        symptoms_repo: SymptomsRepository,
        conversation_repo: ConversationRepository,
        llm_service: LLMService,
        citation_service: CitationService,
        rag_retriever: Callable,
        period_repo: Optional[PeriodRepository] = None,
    ):
        self.user_repo = user_repo
        self.symptoms_repo = symptoms_repo
        self.conversation_repo = conversation_repo
        self.llm_service = llm_service
        self.citation_service = citation_service
        self.rag_retriever = rag_retriever
        self.period_repo = period_repo
        self._prompt_config: Optional[dict] = None

    # ---------------------------------------------------------------------------
    # ask()
    # ---------------------------------------------------------------------------

    async def ask(
        self,
        user_id: str,
        message: str,
        conversation_id: UUID | None = None,
    ) -> ChatResponse:
        """Process an Ask Meno question with RAG grounding.

        Orchestrates:
        1. Fetch user context and symptom summary
        2. Load existing conversation for storage continuity
        3. Retrieve and deduplicate RAG chunks
        4. Build LLM prompt with context
        5. Call LLM
        6. Sanitize and extract citations
        7. Persist updated conversation
        8. Return typed response

        Args:
            user_id: Authenticated user ID.
            message: Non-empty user question (pre-stripped by caller).
            conversation_id: Existing conversation UUID to append to, or None for new.

        Returns:
            ChatResponse with message text, citations, and conversation_id.

        Raises:
            DatabaseError: User context, symptom summary, conversation load, or save fails.
        """
        # Fetch user context and symptom summary
        try:
            journey_stage, age = await self.user_repo.get_context(user_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch user context: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to process question: {exc}") from exc

        try:
            symptom_summary = await self.symptoms_repo.get_summary(user_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch symptom summary: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to process question: {exc}") from exc

        # Fetch cycle data if available — used to enrich Layer 4 context
        cycle_context: Optional[dict] = None
        has_uterus: Optional[bool] = None
        if self.period_repo is not None:
            try:
                analysis_result, settings_result = await asyncio.gather(
                    self.period_repo.get_cycle_analysis(user_id),
                    self.user_repo.get_settings(user_id),
                    return_exceptions=True,
                )
                if not isinstance(settings_result, Exception):
                    has_uterus = settings_result.has_uterus
                if not isinstance(analysis_result, Exception) and analysis_result is not None:
                    cycle_context = {
                        "average_cycle_length": analysis_result.average_cycle_length,
                        "months_since_last_period": analysis_result.months_since_last_period,
                        "inferred_stage": analysis_result.inferred_stage,
                    }
            except Exception:
                pass  # Cycle data is supplementary — degrade gracefully

        # Load existing conversation messages (for storage continuity — not sent to LLM)
        existing_messages: list[dict] = []
        if conversation_id is not None:
            existing_messages = await self.conversation_repo.load(
                conversation_id, user_id
            )

        # RAG retrieval
        logger.info(
            "RAG: Starting retrieval for user=%s query_len=%d",
            hash_user_id(user_id),
            safe_len(message),
        )
        try:
            chunks = await self.rag_retriever(message, top_k=5)
            if chunks:
                logger.info(
                    "RAG: Success — %d chunks retrieved for user=%s",
                    len(chunks),
                    hash_user_id(user_id),
                )
            else:
                logger.warning(
                    "RAG: Empty result for user=%s query_len=%d — response will have no source grounding",
                    hash_user_id(user_id),
                    safe_len(message),
                )
        except Exception as exc:
            logger.error(
                "RAG: Retrieval failed for user=%s query_len=%d: %s",
                hash_user_id(user_id),
                safe_len(message),
                exc,
                exc_info=True,
            )
            chunks = []  # Degrade gracefully — answer without sources

        # Deduplicate chunks by URL+section (keep first occurrence of each unique pair)
        seen_url_sections: set[tuple[str, str]] = set()
        unique_chunks: list[dict] = []
        for chunk in chunks:
            url = chunk.get("source_url", "")
            section = chunk.get("section_name", "") or "default"
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
        system_prompt = PromptService.build_system_prompt(
            journey_stage, age, symptom_summary, chunks,
            cycle_context=cycle_context, has_uterus=has_uterus,
        )

        # Call LLM (JSON mode, lower temperature for source faithfulness)
        try:
            response_text = await self.llm_service.provider.chat_completion(
                system_prompt=system_prompt,
                user_prompt=message,
                response_format="json",
                temperature=0.3,
                max_tokens=1500,
            )
        except Exception as exc:
            logger.error(
                "LLM call failed for user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError("LLM call failed") from exc

        logger.info(
            "LLM completed: user=%s chunks=%d response_len=%d",
            hash_user_id(user_id),
            len(chunks),
            safe_len(response_text),
        )

        # Parse structured JSON response and render with verified citations
        try:
            raw_response = json.loads(response_text)

            # Log the raw structured response for debugging citation issues
            logger.info(
                "Raw structured LLM response for user=%s: %s",
                hash_user_id(user_id),
                json.dumps(raw_response, indent=None)[:2000],
            )

            structured = StructuredLLMResponse(**raw_response)
            response_text, citations = self.citation_service.render_structured_response(
                structured, chunks
            )

            # Log the final rendered text so we can verify no stray markers
            logger.info(
                "Rendered text for user=%s: %s",
                hash_user_id(user_id),
                response_text[:500],
            )
            logger.info(
                "Structured response rendered: %d citation(s) for user=%s",
                len(citations),
                hash_user_id(user_id),
            )
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning(
                "Failed to parse structured LLM response for user=%s (%s: %s) — "
                "falling back to free-text pipeline",
                hash_user_id(user_id),
                type(exc).__name__,
                exc,
            )
            # Fallback: run old sanitize → verify → extract pipeline on raw text
            sanitize_result = self.citation_service.sanitize_and_renumber(
                response_text, len(chunks)
            )
            response_text = sanitize_result.text
            response_text, stripped = self.citation_service.verify_citations(
                response_text, chunks
            )
            if stripped:
                logger.warning(
                    "Fallback pipeline stripped %d citations for user=%s",
                    len(stripped),
                    hash_user_id(user_id),
                )
            citations = self.citation_service.extract(response_text, chunks)
            logger.info(
                "Fallback pipeline extracted %d citation(s) for user=%s",
                len(citations),
                hash_user_id(user_id),
            )

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
        try:
            saved_conversation_id = await self.conversation_repo.save(
                conversation_id, user_id, updated_messages
            )
        except Exception as exc:
            logger.error(
                "Failed to persist conversation for user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to save conversation: {exc}") from exc

        return ChatResponse(
            message=response_text,
            citations=citations,
            conversation_id=saved_conversation_id,
        )

    # ---------------------------------------------------------------------------
    # get_suggested_prompts()
    # ---------------------------------------------------------------------------

    async def get_suggested_prompts(
        self,
        user_id: str,
        days_back: int = 30,
        max_prompts: int = 6,
    ) -> SuggestedPromptsResponse:
        """Get personalized starter prompts based on recent symptoms.

        Fetches user's recent symptom logs, looks up prompts for those symptoms,
        and returns up to max_prompts (filled with general prompts if needed).

        Args:
            user_id: User ID.
            days_back: Look back N days for symptoms (default 30).
            max_prompts: Maximum prompts to return (default 6).

        Returns:
            SuggestedPromptsResponse with up to max_prompts prompt strings.

        Raises:
            DatabaseError: If symptom fetch fails.
        """
        logger.info(
            "Getting suggested prompts for user: %s (days_back=%d)",
            hash_user_id(user_id),
            days_back,
        )

        try:
            start_date, end_date = get_date_range(days_back)
            logs, _ = await self.symptoms_repo.get_logs(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Extract unique symptom names from logs
            symptom_names = set()
            for log in logs:
                for symptom_detail in log.symptoms:
                    symptom_names.add(symptom_detail.name)

            logger.debug(
                "Extracted %d unique symptoms from %d logs",
                len(symptom_names),
                len(logs),
            )

            prompt_config = self._load_prompt_config()

            prompts = []

            # Add symptom-specific prompts
            for symptom in symptom_names:
                if symptom in prompt_config:
                    symptom_prompts = prompt_config[symptom]
                    selected_count = min(2, len(symptom_prompts))
                    selected = random.sample(symptom_prompts, selected_count)
                    prompts.extend(selected)

            # Fill with general prompts if needed
            if len(prompts) < max_prompts:
                general = prompt_config.get("general", [])
                needed = max_prompts - len(prompts)
                if general:
                    additional_count = min(needed, len(general))
                    additional = random.sample(general, additional_count)
                    prompts.extend(additional)

            # Deduplicate while preserving order, cap at max_prompts
            seen: set[str] = set()
            final_prompts = []
            for prompt in prompts:
                if prompt not in seen:
                    final_prompts.append(prompt)
                    seen.add(prompt)
                if len(final_prompts) >= max_prompts:
                    break

            logger.info(
                safe_summary(
                    "get suggested prompts", "success", count=len(final_prompts)
                )
            )

            return SuggestedPromptsResponse(prompts=final_prompts)

        except DatabaseError:
            logger.error("Failed to fetch symptoms for prompts")
            raise
        except Exception as exc:
            logger.error("Failed to generate prompts: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to generate prompts: {str(exc)}") from exc

    def _load_prompt_config(self) -> dict:
        """Load prompt config from JSON file, caching on first call."""
        if self._prompt_config is not None:
            return self._prompt_config

        config_path = (
            Path(__file__).parent.parent.parent / "config" / "starter_prompts.json"
        )

        try:
            with open(config_path) as f:
                config_data = json.load(f)
                loaded: dict = config_data.get("starter_prompts", {})
                self._prompt_config = loaded
                logger.debug("Loaded prompt config: %d symptom groups", len(loaded))
                return loaded
        except FileNotFoundError:
            logger.error("Prompt config file not found: %s", config_path)
            self._prompt_config = {}
            return {}
        except json.JSONDecodeError:
            logger.error("Failed to parse prompt config: %s", config_path)
            self._prompt_config = {}
            return {}

    # ---------------------------------------------------------------------------
    # Conversation history
    # ---------------------------------------------------------------------------

    async def list_conversations(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ConversationListResponse:
        """List all conversations for a user, sorted by most recent first.

        Args:
            user_id: Authenticated user ID.
            limit: Max conversations to return (1-100).
            offset: Pagination offset.

        Returns:
            ConversationListResponse with summaries, total, and pagination info.

        Raises:
            DatabaseError: If database query fails.
        """
        rows, total = await self.conversation_repo.list(user_id, limit, offset)

        conversations = [
            ConversationSummary(
                id=UUID(row["id"]),
                title=build_conversation_title(row.get("messages") or []),
                created_at=row["created_at"],
                message_count=len(row.get("messages") or []),
            )
            for row in rows
        ]

        return ConversationListResponse(
            conversations=conversations,
            total=total,
            has_more=offset + limit < total,
            limit=limit,
            offset=offset,
        )

    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: str,
    ) -> ConversationMessagesResponse:
        """Load a specific conversation's messages for resuming.

        Args:
            conversation_id: UUID of the conversation to load.
            user_id: Authenticated user ID (for ownership check).

        Returns:
            ConversationMessagesResponse with full message history.

        Raises:
            EntityNotFoundError: If conversation doesn't exist or doesn't belong to user.
            DatabaseError: If database query fails.
        """
        messages = await self.conversation_repo.load(conversation_id, user_id)
        return ConversationMessagesResponse(
            conversation_id=conversation_id,
            messages=[ChatMessage(**m) for m in messages],
        )

    async def delete_conversation(
        self,
        conversation_id: UUID,
        user_id: str,
    ) -> None:
        """Delete a conversation permanently.

        Args:
            conversation_id: UUID of the conversation to delete.
            user_id: Authenticated user ID (for ownership check).

        Raises:
            EntityNotFoundError: If conversation doesn't exist or doesn't belong to user.
            DatabaseError: If database delete fails.
        """
        await self.conversation_repo.delete(conversation_id, user_id)
