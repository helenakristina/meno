"""Data access layer for User entity.

Handles all Supabase queries for user profile data.
Keeps data access logic out of routes and services.
"""

import logging
from typing import Optional

from fastapi import HTTPException, status
from supabase import AsyncClient

from app.utils.dates import calculate_age

logger = logging.getLogger(__name__)


class UserRepository:
    """Data access for User entity.

    Handles all Supabase queries for user profiles.
    Enforces user ownership on all queries.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def get_context(self, user_id: str) -> tuple[str, int | None]:
        """Get user journey stage and calculated age for Ask Meno context.

        Args:
            user_id: ID of the user.

        Returns:
            Tuple of (journey_stage, age). Falls back to ("unsure", None) gracefully
            if user data is missing or incomplete.

        Raises:
            HTTPException: 500 if database query fails.
        """
        try:
            response = (
                await self.client.table("users")
                .select("journey_stage, date_of_birth")
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed fetching user context for %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user context",
            )

        if not response.data:
            logger.warning("User context not found for user %s", user_id)
            return "unsure", None

        row = response.data[0]
        journey_stage = row.get("journey_stage") or "unsure"

        dob_raw = row.get("date_of_birth")
        age = None
        if dob_raw:
            try:
                age = calculate_age(dob_raw)
            except ValueError as e:
                logger.warning("Invalid DOB for user %s: %s", user_id, e)
                age = None

        return journey_stage, age

    async def get_profile(self, user_id: str) -> dict:
        """Fetch complete user profile.

        Args:
            user_id: ID of the user.

        Returns:
            User profile dict with all fields (id, email, date_of_birth, journey_stage,
            insurance_type, insurance_plan_name, onboarding_completed, created_at).

        Raises:
            HTTPException: 404 if user not found.
            HTTPException: 500 if database query fails.
        """
        try:
            response = (
                await self.client.table("users")
                .select("*")
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed fetching user profile for %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user profile",
            )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.debug("User profile fetched for user %s", user_id)
        return response.data[0]

    async def update_profile(self, user_id: str, data: dict) -> dict:
        """Update user profile fields.

        Args:
            user_id: ID of the user.
            data: Fields to update (id and user_id should not be included).

        Returns:
            Updated user profile dict.

        Raises:
            HTTPException: 404 if user not found.
            HTTPException: 500 if database update fails.
        """
        try:
            response = (
                await self.client.table("users")
                .update(data)
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile",
            )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.info("User profile updated for user %s", user_id)
        return response.data[0]

    async def create(self, user_id: str, email: str, data: dict) -> dict:
        """Create a new user profile.

        Args:
            user_id: UUID of the authenticated user (from Supabase Auth).
            email: User's email (from Supabase Auth, trusted source).
            data: Additional profile data (date_of_birth, journey_stage, etc.).

        Returns:
            Created user profile dict.

        Raises:
            HTTPException: 409 if user already exists.
            HTTPException: 500 if database insert fails.
        """
        try:
            response = (
                await self.client.table("users")
                .insert(
                    {
                        "id": user_id,
                        "email": email,
                        **data,
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB insert failed creating user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            # Check if it's a conflict (duplicate) error
            if "duplicate key" in str(exc).lower() or "unique violation" in str(exc).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User profile already exists",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user profile",
            )

        if not response.data:
            logger.error("Supabase returned no data after user insert")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user profile",
            )

        created = response.data[0]
        logger.info("User profile created: id=%s email=%s", user_id, email)
        return created

    async def get(self, user_id: str) -> Optional[dict]:
        """Fetch a single user by ID.

        Args:
            user_id: ID of user to fetch.

        Returns:
            User dict or None if not found.

        Raises:
            HTTPException: 500 if database query fails.
        """
        try:
            response = (
                await self.client.table("users")
                .select("*")
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed fetching user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user",
            )

        if not response.data:
            return None

        return response.data[0]

    async def delete(self, user_id: str) -> None:
        """Delete a user profile (soft or hard depending on RLS policy).

        Args:
            user_id: ID of user to delete.

        Raises:
            HTTPException: 404 if user not found.
            HTTPException: 500 if database delete fails.
        """
        try:
            response = (
                await self.client.table("users")
                .delete()
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB delete failed for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user",
            )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.info("User deleted: id=%s", user_id)
