"""Data access layer for User entity.

Handles all Supabase queries for user profile data.
Keeps data access logic out of routes and services.
"""

import logging
from typing import Optional

from supabase import AsyncClient

from app.exceptions import DatabaseError, DuplicateEntityError, EntityNotFoundError
from app.models.users import UserProfile, UserSettingsResponse, UserSettingsUpdate
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
            DatabaseError: If database query fails.
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
            raise DatabaseError(f"Failed to fetch user context: {exc}") from exc

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

    async def get_profile(self, user_id: str) -> UserProfile:
        """Fetch complete user profile.

        Args:
            user_id: ID of the user.

        Returns:
            UserProfile with all fields.

        Raises:
            EntityNotFoundError: If user not found.
            DatabaseError: If database query fails.
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
            raise DatabaseError(f"Failed to fetch user profile: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("User not found")

        logger.debug("User profile fetched for user %s", user_id)
        return UserProfile(**response.data[0])

    async def update_profile(self, user_id: str, data: dict) -> UserProfile:
        """Update user profile fields.

        Args:
            user_id: ID of the user.
            data: Fields to update (id and user_id should not be included).

        Returns:
            Updated UserProfile.

        Raises:
            EntityNotFoundError: If user not found.
            DatabaseError: If database update fails.
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
            raise DatabaseError(f"Failed to update user profile: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("User not found")

        logger.info("User profile updated for user %s", user_id)
        return UserProfile(**response.data[0])

    async def create(self, user_id: str, email: str, data: dict) -> UserProfile:
        """Create a new user profile.

        Args:
            user_id: UUID of the authenticated user (from Supabase Auth).
            email: User's email (from Supabase Auth, trusted source).
            data: Additional profile data (date_of_birth, journey_stage, etc.).

        Returns:
            Created UserProfile.

        Raises:
            DuplicateEntityError: If user already exists.
            DatabaseError: If database insert fails.
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
                raise DuplicateEntityError("User profile already exists") from exc
            raise DatabaseError(f"Failed to create user profile: {exc}") from exc

        if not response.data:
            logger.error("Supabase returned no data after user insert")
            raise DatabaseError("Failed to create user profile: no data returned")

        logger.info("User profile created: id=%s email=%s", user_id, email)
        return UserProfile(**response.data[0])

    async def get(self, user_id: str) -> Optional[UserProfile]:
        """Fetch a single user by ID.

        Args:
            user_id: ID of user to fetch.

        Returns:
            UserProfile or None if not found.

        Raises:
            DatabaseError: If database query fails.
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
            raise DatabaseError(f"Failed to fetch user: {exc}") from exc

        if not response.data:
            return None

        return UserProfile(**response.data[0])

    async def get_settings(self, user_id: str) -> UserSettingsResponse:
        """Fetch user settings: period_tracking_enabled, has_uterus, journey_stage.

        Args:
            user_id: ID of the user.

        Returns:
            UserSettingsResponse with current settings.

        Raises:
            EntityNotFoundError: If user not found.
            DatabaseError: If database query fails.
        """
        try:
            response = (
                await self.client.table("users")
                .select("period_tracking_enabled, has_uterus, journey_stage")
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed fetching settings user=%s: %s", user_id, exc, exc_info=True)
            raise DatabaseError(f"Failed to fetch user settings: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("User not found")

        row = response.data[0]
        return UserSettingsResponse(
            period_tracking_enabled=row.get("period_tracking_enabled", True),
            has_uterus=row.get("has_uterus"),
            journey_stage=row.get("journey_stage"),
        )

    async def update_settings(self, user_id: str, data: UserSettingsUpdate) -> UserSettingsResponse:
        """Update user settings fields.

        If has_uterus is set to False, period_tracking_enabled is also set to False.

        Args:
            user_id: ID of the user.
            data: Settings fields to update.

        Returns:
            Updated UserSettingsResponse.

        Raises:
            EntityNotFoundError: If user not found.
            DatabaseError: If database update fails.
        """
        update_data: dict = {}
        if data.period_tracking_enabled is not None:
            update_data["period_tracking_enabled"] = data.period_tracking_enabled
        if data.has_uterus is not None:
            update_data["has_uterus"] = data.has_uterus
            # If user indicates no uterus, disable period tracking automatically
            if data.has_uterus is False:
                update_data["period_tracking_enabled"] = False
        if data.journey_stage is not None:
            update_data["journey_stage"] = data.journey_stage

        try:
            response = (
                await self.client.table("users")
                .update(update_data)
                .eq("id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB update failed for settings user=%s: %s", user_id, exc, exc_info=True)
            raise DatabaseError(f"Failed to update user settings: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("User not found")

        row = response.data[0]
        logger.info("User settings updated: user=%s", user_id)
        return UserSettingsResponse(
            period_tracking_enabled=row.get("period_tracking_enabled", True),
            has_uterus=row.get("has_uterus"),
            journey_stage=row.get("journey_stage"),
        )

    async def delete(self, user_id: str) -> None:
        """Delete a user profile (soft or hard depending on RLS policy).

        Args:
            user_id: ID of user to delete.

        Raises:
            EntityNotFoundError: If user not found.
            DatabaseError: If database delete fails.
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
            raise DatabaseError(f"Failed to delete user: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("User not found")

        logger.info("User deleted: id=%s", user_id)
