"""Data access layer for Appointment Prep entity.

Handles all Supabase queries for appointment prep contexts and outputs.
Keeps data access logic out of routes and services.
"""

import logging
from typing import Any, Optional

from fastapi import HTTPException, status
from supabase import AsyncClient

from app.models.appointment import (
    AppointmentContext,
    ProviderSummary,
    PersonalCheatSheet,
)

logger = logging.getLogger(__name__)


class AppointmentRepository:
    """Data access for Appointment Prep entity.

    Handles all Supabase queries for appointment prep contexts and outputs.
    Enforces user ownership on all queries.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def save_context(self, user_id: str, context: AppointmentContext) -> str:
        """Save appointment prep context (Step 1 selections).

        Creates a new appointment prep context with the user's selections for
        appointment type, goal, and dismissal experience.

        Args:
            user_id: ID of the user creating the appointment prep.
            context: AppointmentContext with appointment_type, goal, dismissed_before.

        Returns:
            UUID string of the created appointment context.

        Raises:
            HTTPException: 500 if the database insert fails.
        """
        try:
            data = {
                "user_id": user_id,
                "appointment_type": context.appointment_type.value,
                "goal": context.goal.value,
                "dismissed_before": context.dismissed_before.value,
            }
            response = (
                await self.client.table("appointment_prep_contexts")
                .insert(data)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB insert failed creating appointment context for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create appointment context",
            )

        if not response.data or not isinstance(response.data, list):
            logger.error(
                "Supabase returned no data after appointment context insert for user %s",
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create appointment context",
            )

        row = response.data[0]
        context_id: str = row["id"]
        logger.info(
            "Appointment context created: id=%s user=%s appointment_type=%s",
            context_id,
            user_id,
            context.appointment_type.value,
        )
        return context_id

    async def get_context(
        self, appointment_id: str, user_id: str
    ) -> AppointmentContext:
        """Fetch appointment prep context by ID.

        Args:
            appointment_id: ID of the appointment context to fetch.
            user_id: ID of the user (for ownership verification).

        Returns:
            AppointmentContext with the retrieved values.

        Raises:
            HTTPException: 404 if the context doesn't exist or doesn't belong to user.
            HTTPException: 500 if the database query fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .select("*")
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed loading appointment context %s for user %s: %s",
                appointment_id,
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch appointment context",
            )

        if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        row: dict[str, Any] = response.data[0]
        return AppointmentContext(
            appointment_type=row["appointment_type"],
            goal=row["goal"],
            dismissed_before=row["dismissed_before"],
        )

    async def save_outputs(
        self,
        appointment_id: str,
        user_id: str,
        provider_summary: ProviderSummary | None = None,
        personal_cheat_sheet: PersonalCheatSheet | None = None,
    ) -> str:
        """Save or update appointment prep outputs (Step 5 results).

        Args:
            appointment_id: ID of the appointment context this output belongs to.
            user_id: ID of the user (for ownership verification).
            provider_summary: ProviderSummary with content and generated_at.
            personal_cheat_sheet: PersonalCheatSheet with content and generated_at.

        Returns:
            UUID string of the output record.

        Raises:
            HTTPException: 404 if appointment context doesn't exist or doesn't belong to user.
            HTTPException: 500 if the database operation fails.
        """
        # Verify context exists and belongs to user
        try:
            context_response = (
                await self.client.table("appointment_prep_contexts")
                .select("id")
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed verifying appointment context %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save appointment outputs",
            )

        if not context_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        # Check if outputs already exist
        try:
            existing = (
                await self.client.table("appointment_prep_outputs")
                .select("id")
                .eq("context_id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed checking for existing outputs: %s",
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save appointment outputs",
            )

        data: dict[str, Any] = {}
        if provider_summary:
            data["provider_summary_content"] = provider_summary.content
            data["provider_summary_generated_at"] = provider_summary.generated_at.isoformat()
        if personal_cheat_sheet:
            data["personal_cheat_sheet_content"] = personal_cheat_sheet.content
            data["personal_cheat_sheet_generated_at"] = (
                personal_cheat_sheet.generated_at.isoformat()
            )

        try:
            if existing.data:
                # Update existing outputs
                output_id = existing.data[0]["id"]
                await (
                    self.client.table("appointment_prep_outputs")
                    .update(data)
                    .eq("id", output_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                logger.info(
                    "Appointment outputs updated: id=%s context=%s",
                    output_id,
                    appointment_id,
                )
                return output_id
            else:
                # Create new outputs
                data["user_id"] = user_id
                data["context_id"] = appointment_id
                response = (
                    await self.client.table("appointment_prep_outputs")
                    .insert(data)
                    .execute()
                )
        except Exception as exc:
            logger.error(
                "DB operation failed for appointment outputs: %s",
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save appointment outputs",
            )

        if not response.data:
            logger.error(
                "Supabase returned no data after outputs insert for appointment %s",
                appointment_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save appointment outputs",
            )

        output_id = response.data[0]["id"]
        logger.info(
            "Appointment outputs created: id=%s context=%s",
            output_id,
            appointment_id,
        )
        return output_id

    async def get_latest(self, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch the user's most recent appointment prep outputs.

        Used to allow resuming an incomplete appointment prep flow.

        Args:
            user_id: ID of the user.

        Returns:
            Dict with full appointment prep data (context + outputs), or None if no prep exists.

        Raises:
            HTTPException: 500 if the database query fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_outputs")
                .select(
                    "*, appointment_prep_contexts(appointment_type, goal, dismissed_before, created_at)"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed fetching latest appointment prep for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch appointment prep",
            )

        if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
            return None

        return response.data[0]

    async def save_narrative(
        self, appointment_id: str, user_id: str, narrative_text: str
    ) -> None:
        """Save the LLM-generated narrative to the appointment context.

        Updates the appointment_prep_contexts.narrative field with the generated narrative.

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).
            narrative_text: The generated narrative text (markdown).

        Raises:
            HTTPException: 404 if the appointment context doesn't exist or doesn't belong to user.
            HTTPException: 500 if the database update fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .update({"narrative": narrative_text})
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed saving narrative for appointment %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save narrative",
            )

        if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        logger.info(
            "Narrative saved: appointment_id=%s narrative_length=%d",
            appointment_id,
            len(narrative_text),
        )

    async def save_concerns(
        self, appointment_id: str, user_id: str, concerns: list[str]
    ) -> None:
        """Save prioritized concerns to the appointment context.

        Updates the appointment_prep_contexts.concerns field with the ranked list.

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).
            concerns: Ordered list of prioritized concerns.

        Raises:
            HTTPException: 404 if the appointment context doesn't exist or doesn't belong to user.
            HTTPException: 500 if the database update fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .update({"concerns": concerns})
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed saving concerns for appointment %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save concerns",
            )

        if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        logger.info(
            "Concerns saved: appointment_id=%s concerns_count=%d",
            appointment_id,
            len(concerns),
        )

    async def save_scenarios(
        self, appointment_id: str, user_id: str, scenarios: list[dict[str, Any]]
    ) -> None:
        """Save scenario cards to the appointment context.

        Updates the appointment_prep_contexts.scenarios field with the scenario list.

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).
            scenarios: List of scenario card dicts with id, title, situation, suggestion, category.

        Raises:
            HTTPException: 404 if the appointment context doesn't exist or doesn't belong to user.
            HTTPException: 500 if the database update fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .update({"scenarios": scenarios})
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed saving scenarios for appointment %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save scenarios",
            )

        if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        logger.info(
            "Scenarios saved: appointment_id=%s scenarios_count=%d",
            appointment_id,
            len(scenarios),
        )
