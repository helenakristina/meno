"""Data access layer for Appointment Prep entity.

Handles all Supabase queries for appointment prep contexts and outputs.
Keeps data access logic out of routes and services.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import AsyncClient

from app.exceptions import DatabaseError, EntityNotFoundError

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
            context: AppointmentContext with appointment_type, goal, dismissed_before, urgent_symptom.

        Returns:
            UUID string of the created appointment context.

        Raises:
            DatabaseError: If the database insert fails.
        """
        try:
            data = {
                "user_id": user_id,
                "appointment_type": context.appointment_type.value,
                "goal": context.goal.value,
                "dismissed_before": context.dismissed_before.value,
                "urgent_symptom": context.urgent_symptom,
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
            raise DatabaseError(f"Failed to create appointment context: {exc}") from exc

        if not response.data or not isinstance(response.data, list):
            logger.error(
                "Supabase returned no data after appointment context insert for user %s",
                user_id,
            )
            raise DatabaseError(
                "Failed to create appointment context: no data returned"
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
            EntityNotFoundError: If the context doesn't exist or doesn't belong to user.
            DatabaseError: If the database query fails.
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
            raise DatabaseError(f"Failed to fetch appointment context: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

        row: dict[str, Any] = response.data[0]
        return AppointmentContext(
            appointment_type=row["appointment_type"],
            goal=row["goal"],
            dismissed_before=row["dismissed_before"],
            urgent_symptom=row.get("urgent_symptom"),
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
            EntityNotFoundError: If appointment context doesn't exist or doesn't belong to user.
            DatabaseError: If the database operation fails.
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
            raise DatabaseError(f"Failed to save appointment outputs: {exc}") from exc

        if not context_response.data:
            raise EntityNotFoundError("Appointment context not found")

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
            raise DatabaseError(f"Failed to save appointment outputs: {exc}") from exc

        data: dict[str, Any] = {}
        if provider_summary:
            data["provider_summary_content"] = provider_summary.content
            data["provider_summary_generated_at"] = (
                provider_summary.generated_at.isoformat()
            )
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
            raise DatabaseError(f"Failed to save appointment outputs: {exc}") from exc

        if not response.data:
            logger.error(
                "Supabase returned no data after outputs insert for appointment %s",
                appointment_id,
            )
            raise DatabaseError("Failed to save appointment outputs: no data returned")

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
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_outputs")
                .select(
                    "*, appointment_prep_contexts(appointment_type, goal, dismissed_before, urgent_symptom, created_at)"
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
            raise DatabaseError(f"Failed to fetch appointment prep: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
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
            EntityNotFoundError: If the appointment context doesn't exist or doesn't belong to user.
            DatabaseError: If the database update fails.
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
            raise DatabaseError(f"Failed to save narrative: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

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
            EntityNotFoundError: If the appointment context doesn't exist or doesn't belong to user.
            DatabaseError: If the database update fails.
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
            raise DatabaseError(f"Failed to save concerns: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

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
            EntityNotFoundError: If the appointment context doesn't exist or doesn't belong to user.
            DatabaseError: If the database update fails.
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
            raise DatabaseError(f"Failed to save scenarios: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

        logger.info(
            "Scenarios saved: appointment_id=%s scenarios_count=%d",
            appointment_id,
            len(scenarios),
        )

    async def save_pdf_metadata(
        self,
        user_id: str,
        appointment_id: str,
        provider_summary_path: str,
        personal_cheatsheet_path: str,
    ) -> str:
        """Save metadata about generated PDFs for history tracking.

        Args:
            user_id: User who generated the prep.
            appointment_id: Associated appointment prep.
            provider_summary_path: Path to provider summary PDF in storage.
            personal_cheatsheet_path: Path to personal cheat sheet PDF in storage.

        Returns:
            Metadata ID.

        Raises:
            DatabaseError: If database operation fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_metadata")
                .insert(
                    {
                        "user_id": user_id,
                        "appointment_id": appointment_id,
                        "provider_summary_path": provider_summary_path,
                        "personal_cheatsheet_path": personal_cheatsheet_path,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .execute()
            )

            if not response.data:
                raise DatabaseError("Failed to save PDF metadata: no data returned")

            metadata_id = response.data[0].get("id")
            logger.info(
                "Saved PDF metadata: appointment_id=%s metadata_id=%s",
                appointment_id,
                metadata_id,
            )
            return metadata_id

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to save PDF metadata: %s",
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to save PDF metadata: {exc}") from exc

    async def save_frequency_stats(
        self,
        appointment_id: str,
        user_id: str,
        frequency_stats: list[dict],
        cooccurrence_stats: list[dict],
    ) -> None:
        """Save serialized frequency and co-occurrence stats to the appointment context.

        Stored as JSONB so Step 5 can retrieve pre-computed stats without re-querying
        symptom logs (which may be sparse or deleted by then).

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).
            frequency_stats: Serialized list of SymptomFrequency dicts.
            cooccurrence_stats: Serialized list of SymptomPair dicts.

        Raises:
            EntityNotFoundError: If the appointment context doesn't exist.
            DatabaseError: If the database update fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .update(
                    {
                        "frequency_stats": frequency_stats,
                        "cooccurrence_stats": cooccurrence_stats,
                    }
                )
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed saving frequency stats for appointment %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to save frequency stats: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

        logger.info(
            "Frequency stats saved: appointment_id=%s freq=%d coocc=%d",
            appointment_id,
            len(frequency_stats),
            len(cooccurrence_stats),
        )

    async def get_symptom_reference(self, symptom_ids: list[str]) -> dict[str, dict]:
        """Fetch symptom reference data for a set of IDs.

        Used by narrative generation to look up symptom names and categories
        for stat calculations.

        Args:
            symptom_ids: List of symptom UUIDs to look up.

        Returns:
            Dict mapping symptom_id → {"name": str, "category": str}.
            Empty dict if symptom_ids is empty.

        Raises:
            DatabaseError: If the database query fails.
        """
        if not symptom_ids:
            return {}
        try:
            response = (
                await self.client.table("symptoms_reference")
                .select("id, name, category")
                .in_("id", symptom_ids)
                .execute()
            )
            return {
                row["id"]: {"name": row["name"], "category": row["category"]}
                for row in (response.data or [])
            }
        except Exception as exc:
            logger.error("Failed to fetch symptom reference: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to fetch symptom reference: {exc}") from exc

    async def get_concerns(self, appointment_id: str, user_id: str) -> list[str]:
        """Fetch prioritized concerns from appointment context.

        Returns the concerns list saved in Step 3. Returns empty list if
        concerns haven't been saved yet (Step 3 not completed).

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).

        Returns:
            List of concern strings, or empty list if not set.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .select("concerns")
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
            if response.data and len(response.data) > 0:
                data = response.data[0]
                if isinstance(data, dict):
                    concerns = data.get("concerns")
                    if isinstance(concerns, list):
                        return concerns
            return []
        except Exception as exc:
            logger.error(
                "Failed to fetch concerns for appointment %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to fetch concerns: {exc}") from exc

    async def get_appointment_data(
        self, appointment_id: str, user_id: str
    ) -> dict[str, Any]:
        """Fetch narrative, concerns, and scenarios from appointment context.

        Used by PDF generation (Step 5) to retrieve all data from earlier steps.

        Args:
            appointment_id: ID of the appointment context.
            user_id: ID of the user (for ownership verification).

        Returns:
            Dict with keys: narrative, concerns, scenarios.

        Raises:
            EntityNotFoundError: If the appointment context doesn't exist or doesn't belong to user.
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("appointment_prep_contexts")
                .select(
                    "narrative, concerns, scenarios, frequency_stats, cooccurrence_stats"
                )
                .eq("id", appointment_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch appointment data for %s: %s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to fetch appointment data: {exc}") from exc

        if (
            not response.data
            or not isinstance(response.data, list)
            or len(response.data) == 0
        ):
            raise EntityNotFoundError("Appointment context not found")

        return response.data[0]

    async def get_user_prep_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get user's appointment prep history (newest first).

        Args:
            user_id: User ID.
            limit: Max results to return (default 50).
            offset: Pagination offset (default 0).

        Returns:
            Tuple of (list of preps, total count).

        Raises:
            DatabaseError: If database operation fails.
        """
        try:
            # Get total count
            count_response = (
                await self.client.table("appointment_prep_metadata")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            total = count_response.count if count_response.count is not None else 0

            # Get paginated results
            response = (
                await self.client.table("appointment_prep_metadata")
                .select("*")
                .eq("user_id", user_id)
                .order("generated_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            preps = (
                response.data
                if response.data and isinstance(response.data, list)
                else []
            )

            logger.info(
                "Fetched appointment prep history: user=%s count=%d total=%d",
                user_id,
                len(preps),
                total,
            )

            return preps, total

        except Exception as exc:
            logger.error(
                "Failed to fetch appointment prep history: %s",
                exc,
                exc_info=True,
            )
            raise DatabaseError(
                f"Failed to fetch appointment prep history: {exc}"
            ) from exc
