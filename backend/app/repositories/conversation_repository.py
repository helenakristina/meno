"""Data access layer for Conversation entity.

Handles all Supabase queries for conversation messages.
Keeps data access logic out of routes and services.
"""

from __future__ import annotations

import logging
from uuid import UUID

from supabase import AsyncClient

from app.exceptions import DatabaseError, EntityNotFoundError
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Data access for Conversation entity.

    Handles all Supabase queries for conversations.
    Enforces user ownership on all queries.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def list(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict], int]:
        """List conversations for a user with pagination.

        Args:
            user_id: ID of the user (for ownership verification).
            limit: Number of conversations to return (1-100).
            offset: Number of conversations to skip for pagination.

        Returns:
            Tuple of (rows, total_count) where rows are conversation dicts.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            response = await (
                self.client.table("conversations")
                .select("id, created_at, messages", count="exact")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed listing conversations for user %s: %s",
                hash_user_id(user_id),
                type(exc).__name__,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to list conversations: {exc}") from exc

        return response.data or [], response.count or 0

    async def load(self, conversation_id: UUID, user_id: str) -> list[dict]:
        """Fetch the messages array from an existing conversation.

        Args:
            conversation_id: ID of conversation to load.
            user_id: ID of the user (for ownership verification).

        Returns:
            List of message dicts, or empty list if conversation is empty.

        Raises:
            EntityNotFoundError: If the conversation doesn't exist or doesn't belong to user.
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("conversations")
                .select("messages")
                .eq("id", str(conversation_id))
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed loading conversation %s for user %s: %s",
                conversation_id,
                hash_user_id(user_id),
                type(exc).__name__,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to load conversation: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Conversation not found")

        return response.data[0].get("messages") or []

    async def save(
        self,
        conversation_id: UUID | None,
        user_id: str,
        messages: list[dict],
    ) -> UUID:
        """Upsert conversation messages.

        Updates an existing conversation if conversation_id is provided,
        or creates a new one if conversation_id is None.

        Args:
            conversation_id: ID of existing conversation, or None to create new.
            user_id: ID of the conversation owner.
            messages: Array of message dicts to store.

        Returns:
            Conversation UUID (either provided or newly created).

        Raises:
            DatabaseError: If the database operation fails.
        """
        if conversation_id is not None:
            try:
                await (
                    self.client.table("conversations")
                    .update({"messages": messages})
                    .eq("id", str(conversation_id))
                    .eq("user_id", user_id)
                    .execute()
                )
            except Exception as exc:
                logger.error(
                    "DB update failed for conversation %s: %s",
                    conversation_id,
                    type(exc).__name__,
                    exc_info=True,
                )
                raise DatabaseError(f"Failed to save conversation: {exc}") from exc
            logger.info(
                "Conversation %s updated for user %s",
                conversation_id,
                hash_user_id(user_id),
            )
            return conversation_id

        # Create new conversation
        try:
            response = (
                await self.client.table("conversations")
                .insert({"user_id": user_id, "messages": messages})
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB insert failed creating conversation for user %s: %s",
                hash_user_id(user_id),
                type(exc).__name__,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to save conversation: {exc}") from exc

        if not response.data:
            logger.error(
                "Supabase returned no data after conversation insert for user %s",
                hash_user_id(user_id),
            )
            raise DatabaseError("Failed to save conversation: no data returned")

        new_id = UUID(response.data[0]["id"])
        logger.info("Conversation created: id=%s user=%s", new_id, user_id)
        return new_id

    async def delete(self, conversation_id: UUID, user_id: str) -> None:
        """Delete a conversation (with ownership check).

        Args:
            conversation_id: ID of conversation to delete.
            user_id: ID of the user (for ownership verification).

        Raises:
            EntityNotFoundError: If conversation not found or doesn't belong to user.
            DatabaseError: If the database delete fails.
        """
        try:
            response = (
                await self.client.table("conversations")
                .delete()
                .eq("id", str(conversation_id))
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB delete failed for conversation %s: %s",
                conversation_id,
                type(exc).__name__,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to delete conversation: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Conversation not found")

        logger.info(
            "Conversation deleted: id=%s user=%s",
            conversation_id,
            hash_user_id(user_id),
        )
