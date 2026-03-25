"""Data access layer for MHT medication tracking.

Handles all Supabase queries for medications_reference and user_medications.
Enforces user ownership on all write operations via double-filter (id + user_id).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone

from supabase import AsyncClient

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.medications import (
    MedicationChangeDose,
    MedicationContext,
    MedicationCreate,
    MedicationReferenceCreate,
    MedicationReferenceResult,
    MedicationResponse,
    MedicationUpdate,
)
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

_RECENT_CHANGE_LOOKBACK_DAYS = 90

# Column lists shared across queries to avoid copy-paste drift
_MED_COLS = "id, medication_ref_id, medication_name, dose, delivery_method, frequency, start_date, end_date, previous_entry_id, notes"
_REF_COLS = "id, brand_name, generic_name, hormone_type, common_forms, common_doses, notes, is_user_created"


def _escape_ilike(value: str) -> str:
    """Escape ILIKE special characters to prevent pattern injection."""
    return re.sub(r"([%_\\])", r"\\\1", value)


class MedicationRepository:
    """Data access for medications_reference and user_medications tables."""

    def __init__(self, client: AsyncClient):
        self.client = client

    # ------------------------------------------------------------------
    # medications_reference queries
    # ------------------------------------------------------------------

    async def search_reference(
        self, query: str, user_id: str
    ) -> list[MedicationReferenceResult]:
        """Search medications_reference by brand name or generic name.

        Returns system entries matching the query plus any user-created entries
        from this user that match. Results are ordered by exact match preference,
        then alphabetically.

        Args:
            query: Search string (ILIKE match against brand_name and generic_name).
            user_id: ID of the requesting user (to include their own created entries).

        Returns:
            List of MedicationReferenceResult ordered by relevance.

        Raises:
            DatabaseError: If the database query fails.
        """
        pattern = f"%{_escape_ilike(query)}%"
        try:
            # Fetch system entries
            sys_resp = (
                await self.client.table("medications_reference")
                .select(_REF_COLS)
                .eq("is_user_created", False)
                .or_(f"brand_name.ilike.{pattern},generic_name.ilike.{pattern}")
                .order("generic_name")
                .limit(20)
                .execute()
            )
            # Fetch user-created entries for this user
            user_resp = (
                await self.client.table("medications_reference")
                .select(_REF_COLS)
                .eq("is_user_created", True)
                .eq("created_by", user_id)
                .or_(f"brand_name.ilike.{pattern},generic_name.ilike.{pattern}")
                .order("generic_name")
                .limit(10)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB search failed on medications_reference: %s", exc, exc_info=True
            )
            raise DatabaseError(
                f"Failed to search medications reference: {exc}"
            ) from exc

        rows = (sys_resp.data or []) + (user_resp.data or [])
        return [MedicationReferenceResult.model_validate(r) for r in rows]

    async def create_reference_entry(
        self, user_id: str, data: MedicationReferenceCreate
    ) -> MedicationReferenceResult:
        """Create a user-created medications_reference entry.

        Args:
            user_id: Creator's user ID (set as created_by).
            data: Reference entry creation data.

        Returns:
            Created MedicationReferenceResult.

        Raises:
            DatabaseError: If the database insert fails.
        """
        row = {
            "generic_name": data.generic_name,
            "hormone_type": data.hormone_type,
            "common_forms": data.common_forms,
            "common_doses": data.common_doses,
            "is_user_created": True,
            "created_by": user_id,
        }
        if data.brand_name is not None:
            row["brand_name"] = data.brand_name
        if data.notes is not None:
            row["notes"] = data.notes

        try:
            response = (
                await self.client.table("medications_reference").insert(row).execute()
            )
        except Exception as exc:
            logger.error(
                "DB insert failed for medications_reference user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(
                f"Failed to create medication reference entry: {exc}"
            ) from exc

        if not response.data:
            raise DatabaseError(
                "Failed to create medication reference entry: no data returned"
            )

        return MedicationReferenceResult.model_validate(response.data[0])

    # ------------------------------------------------------------------
    # user_medications queries
    # ------------------------------------------------------------------

    async def list_all(self, user_id: str) -> list[MedicationResponse]:
        """List all medication stints for a user (active + past), newest first.

        Args:
            user_id: Owner's user ID.

        Returns:
            List of MedicationResponse ordered by start_date DESC.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            response = (
                await self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("user_id", user_id)
                .order("start_date", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB list failed for user_medications user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to list medications: {exc}") from exc

        return [MedicationResponse.model_validate(r) for r in (response.data or [])]

    async def get(self, user_id: str, medication_id: str) -> MedicationResponse:
        """Fetch a single medication stint by ID.

        Double-filters by id AND user_id (IDOR protection).

        Args:
            user_id: Owner's user ID.
            medication_id: Medication stint UUID.

        Returns:
            MedicationResponse.

        Raises:
            EntityNotFoundError: If not found or not owned by user.
            DatabaseError: If the query fails.
        """
        try:
            response = (
                await self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("id", medication_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB get failed for user_medications user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to get medication: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Medication not found")

        return MedicationResponse.model_validate(response.data[0])

    async def create(self, user_id: str, data: MedicationCreate) -> MedicationResponse:
        """Create a new medication stint.

        Args:
            user_id: Owner's user ID.
            data: Medication creation data.

        Returns:
            Created MedicationResponse.

        Raises:
            DatabaseError: If the insert fails.
        """
        row: dict = {
            "user_id": user_id,
            "medication_name": data.medication_name,
            "dose": data.dose,
            "delivery_method": data.delivery_method,
            "start_date": data.start_date.isoformat(),
        }
        if data.medication_ref_id is not None:
            row["medication_ref_id"] = data.medication_ref_id
        if data.frequency is not None:
            row["frequency"] = data.frequency
        if data.notes is not None:
            row["notes"] = data.notes

        try:
            response = await self.client.table("user_medications").insert(row).execute()
        except Exception as exc:
            logger.error(
                "DB insert failed for user_medications user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to create medication: {exc}") from exc

        if not response.data:
            raise DatabaseError("Failed to create medication: no data returned")

        logger.info("Medication created user=%s count=1", hash_user_id(user_id))
        return MedicationResponse.model_validate(response.data[0])

    async def update(
        self, user_id: str, medication_id: str, data: MedicationUpdate
    ) -> MedicationResponse:
        """Update allowed fields on a medication stint (notes and/or end_date only).

        Double-filters by id AND user_id (IDOR protection).
        Uses model_dump(exclude_unset=True) so omitted fields are never overwritten,
        and explicit null (e.g. end_date=null) correctly clears the field.

        Args:
            user_id: Owner's user ID.
            medication_id: Medication stint UUID.
            data: Fields to update (only notes and end_date are accepted).

        Returns:
            Updated MedicationResponse.

        Raises:
            EntityNotFoundError: If not found or not owned by user.
            DatabaseError: If the update fails.
        """
        update_data = data.model_dump(exclude_unset=True)
        # Serialize date to ISO string if present
        if "end_date" in update_data and update_data["end_date"] is not None:
            update_data["end_date"] = update_data["end_date"].isoformat()
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            response = (
                await self.client.table("user_medications")
                .update(update_data)
                .eq("id", medication_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed for user_medications user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to update medication: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Medication not found")

        return MedicationResponse.model_validate(response.data[0])

    async def change_dose(
        self,
        user_id: str,
        medication_id: str,
        data: MedicationChangeDose,
        medication_name: str,
        medication_ref_id: str | None,
    ) -> str:
        """Atomically end the current stint and create a new one via Postgres RPC.

        The RPC function handles both writes in a single transaction. If either
        write fails, the entire operation rolls back.

        Args:
            user_id: Owner's user ID.
            medication_id: ID of the active stint being changed.
            data: New dose/method/frequency and effective date.
            medication_name: Denormalized medication name (carried from old stint).
            medication_ref_id: Reference table ID (carried from old stint).

        Returns:
            UUID of the newly created stint.

        Raises:
            EntityNotFoundError: If the old stint is not found or not active.
            DatabaseError: If the RPC call fails.
        """
        try:
            response = await self.client.rpc(
                "change_medication_dose",
                {
                    "p_old_id": medication_id,
                    "p_user_id": user_id,
                    "p_effective_date": data.effective_date.isoformat(),
                    "p_new_dose": data.dose,
                    "p_new_delivery": data.delivery_method,
                    "p_new_frequency": data.frequency,
                    "p_new_notes": data.notes,
                    "p_ref_id": medication_ref_id,
                    "p_medication_name": medication_name,
                },
            ).execute()
        except Exception as exc:
            msg = str(exc)
            if "medication_not_found" in msg:
                raise EntityNotFoundError("Active medication stint not found") from exc
            logger.error(
                "RPC change_medication_dose failed user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to change medication dose: {exc}") from exc

        return str(response.data)

    async def delete(self, user_id: str, medication_id: str) -> None:
        """Delete a medication stint.

        Double-filters by id AND user_id (IDOR protection).

        Args:
            user_id: Owner's user ID.
            medication_id: Medication stint UUID.

        Raises:
            EntityNotFoundError: If not found or not owned by user.
            DatabaseError: If the delete fails.
        """
        # Verify existence first so we can raise 404 vs 500
        await self.get(user_id, medication_id)

        try:
            await (
                self.client.table("user_medications")
                .delete()
                .eq("id", medication_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB delete failed for user_medications user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to delete medication: {exc}") from exc

        logger.info("Medication deleted user=%s", hash_user_id(user_id))

    async def list_current(self, user_id: str) -> list[MedicationResponse]:
        """Return only currently active medication stints (end_date IS NULL).

        Used by integration consumers (Ask Meno, Appointment Prep, Export).

        Args:
            user_id: Owner's user ID.

        Returns:
            List of active MedicationResponse, oldest first.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            response = (
                await self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("user_id", user_id)
                .is_("end_date", "null")
                .order("start_date")
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB list_current failed user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to list current medications: {exc}") from exc

        return [MedicationResponse.model_validate(r) for r in (response.data or [])]

    async def get_context(
        self, user_id: str, lookback_days: int = _RECENT_CHANGE_LOOKBACK_DAYS
    ) -> MedicationContext:
        """Fetch medication context for LLM injection.

        Returns currently active medications and medications stopped within
        the lookback window (recently stopped are still relevant context).

        Args:
            user_id: Owner's user ID.
            lookback_days: How many days back to look for stopped medications.

        Returns:
            MedicationContext with current and recently-stopped medications.

        Raises:
            DatabaseError: If either query fails.
        """
        cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

        try:
            current_resp, recent_resp = await asyncio.gather(
                self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("user_id", user_id)
                .is_("end_date", "null")
                .order("start_date")
                .execute(),
                self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("user_id", user_id)
                .not_.is_("end_date", "null")
                .gte("end_date", cutoff)
                .order("end_date", desc=True)
                .limit(5)
                .execute(),
            )
        except Exception as exc:
            logger.error(
                "DB get_context failed user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to get medication context: {exc}") from exc

        return MedicationContext(
            current_medications=[
                MedicationResponse.model_validate(r) for r in (current_resp.data or [])
            ],
            recent_changes=[
                MedicationResponse.model_validate(r) for r in (recent_resp.data or [])
            ],
        )

    async def list_active_during(
        self, user_id: str, range_start: date, range_end: date
    ) -> list[MedicationResponse]:
        """Return medications active at any point within a date range.

        Uses: start_date <= range_end AND (end_date IS NULL OR end_date >= range_start).
        Used by the PDF export service.

        Args:
            user_id: Owner's user ID.
            range_start: Start of the date range.
            range_end: End of the date range.

        Returns:
            List of MedicationResponse ordered by start_date.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            response = (
                await self.client.table("user_medications")
                .select(_MED_COLS)
                .eq("user_id", user_id)
                .lte("start_date", range_end.isoformat())
                .or_(f"end_date.is.null,end_date.gte.{range_start.isoformat()}")
                .order("start_date")
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB list_active_during failed user=%s: %s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(
                f"Failed to list medications for date range: {exc}"
            ) from exc

        return [MedicationResponse.model_validate(r) for r in (response.data or [])]
