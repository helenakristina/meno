"""Data access layer for Period entity.

Handles all Supabase queries for period logs and cycle analysis.
Keeps data access logic out of routes and services.
"""

import logging
from datetime import date
from typing import Optional

from supabase import AsyncClient

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.period import CycleAnalysisResponse, PeriodLogCreate, PeriodLogResponse, PeriodLogUpdate
from app.utils.dates import calculate_cycle_length
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)


class PeriodRepository:
    """Data access for Period entity.

    Handles all Supabase queries for period logs and cycle analysis.
    Enforces user ownership on all queries.
    """

    def __init__(self, client: AsyncClient):
        self.client = client

    async def create_log(self, user_id: str, data: PeriodLogCreate) -> PeriodLogResponse:
        """Create a new period log entry.

        Args:
            user_id: Owner of the log.
            data: Period log creation data.

        Returns:
            Created PeriodLogResponse.

        Raises:
            DatabaseError: If the database insert fails.
        """
        # Fetch previous log to calculate cycle length
        previous = await self.get_latest_log(user_id)
        cycle_length: Optional[int] = None
        if previous is not None:
            try:
                cycle_length = calculate_cycle_length(data.period_start, previous.period_start)
            except ValueError:
                cycle_length = None

        row: dict = {
            "user_id": user_id,
            "period_start": data.period_start.isoformat(),
            "cycle_length": cycle_length,
        }
        if data.period_end is not None:
            row["period_end"] = data.period_end.isoformat()
        if data.flow_level is not None:
            row["flow_level"] = data.flow_level
        if data.notes is not None:
            row["notes"] = data.notes

        try:
            response = await self.client.table("period_logs").insert(row).execute()
        except Exception as exc:
            logger.error("DB insert failed for period log user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to create period log: {exc}") from exc

        if not response.data:
            raise DatabaseError("Failed to create period log: no data returned")

        logger.info("Period log created: user=%s", hash_user_id(user_id))
        return self._to_model(response.data[0])

    async def get_logs(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[PeriodLogResponse]:
        """Fetch period logs for a user with optional date filtering.

        Args:
            user_id: ID of the user.
            start_date: Include logs on or after this date.
            end_date: Include logs on or before this date.

        Returns:
            List of PeriodLogResponse ordered by period_start descending.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            query = (
                self.client.table("period_logs")
                .select("*")
                .eq("user_id", user_id)
            )
            if start_date is not None:
                query = query.gte("period_start", start_date.isoformat())
            if end_date is not None:
                query = query.lte("period_start", end_date.isoformat())

            query = query.order("period_start", desc=True)
            response = await query.execute()
        except Exception as exc:
            logger.error("DB query failed fetching period logs user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to retrieve period logs: {exc}") from exc

        return [self._to_model(row) for row in (response.data or [])]

    async def get_latest_log(self, user_id: str) -> Optional[PeriodLogResponse]:
        """Fetch the most recent period log for a user.

        Args:
            user_id: ID of the user.

        Returns:
            Most recent PeriodLogResponse, or None if no logs exist.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("period_logs")
                .select("*")
                .eq("user_id", user_id)
                .order("period_start", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed fetching latest period log user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to retrieve latest period log: {exc}") from exc

        if not response.data:
            return None
        return self._to_model(response.data[0])

    async def get_all_logs(self, user_id: str) -> list[PeriodLogResponse]:
        """Fetch all period logs for a user, ordered by period_start.

        Used for cycle analysis calculations.

        Args:
            user_id: ID of the user.

        Returns:
            All PeriodLogResponse records ordered by period_start ascending.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("period_logs")
                .select("*")
                .eq("user_id", user_id)
                .order("period_start", desc=False)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed fetching all period logs user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to retrieve period logs: {exc}") from exc

        return [self._to_model(row) for row in (response.data or [])]

    async def get_log(self, user_id: str, log_id: str) -> PeriodLogResponse:
        """Fetch a single period log by ID.

        Args:
            user_id: Owner of the log (enforces ownership).
            log_id: ID of the log to fetch.

        Returns:
            PeriodLogResponse.

        Raises:
            EntityNotFoundError: If the log does not exist for this user.
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("period_logs")
                .select("*")
                .eq("id", log_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed fetching period log %s user=%s: %s", log_id, hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to retrieve period log: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Period log not found")

        return self._to_model(response.data[0])

    async def update_log(
        self, user_id: str, log_id: str, data: PeriodLogUpdate
    ) -> PeriodLogResponse:
        """Update an existing period log.

        Args:
            user_id: Owner of the log (enforces ownership).
            log_id: ID of the log to update.
            data: Fields to update.

        Returns:
            Updated PeriodLogResponse.

        Raises:
            EntityNotFoundError: If the log does not exist for this user.
            DatabaseError: If the database update fails.
        """
        update_data: dict = {}
        if "period_end" in data.model_fields_set:
            update_data["period_end"] = data.period_end.isoformat() if data.period_end is not None else None
        if "flow_level" in data.model_fields_set:
            update_data["flow_level"] = data.flow_level
        if "notes" in data.model_fields_set:
            update_data["notes"] = data.notes

        try:
            response = (
                await self.client.table("period_logs")
                .update(update_data)
                .eq("id", log_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB update failed for period log %s user=%s: %s", log_id, hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to update period log: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Period log not found")

        logger.info("Period log updated: id=%s user=%s", log_id, hash_user_id(user_id))
        return self._to_model(response.data[0])

    async def delete_log(self, user_id: str, log_id: str) -> None:
        """Delete a period log.

        Args:
            user_id: Owner of the log (enforces ownership).
            log_id: ID of the log to delete.

        Raises:
            EntityNotFoundError: If the log does not exist for this user.
            DatabaseError: If the database delete fails.
        """
        try:
            response = (
                await self.client.table("period_logs")
                .delete()
                .eq("id", log_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error("DB delete failed for period log %s user=%s: %s", log_id, hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to delete period log: {exc}") from exc

        if not response.data:
            raise EntityNotFoundError("Period log not found")

        logger.info("Period log deleted: id=%s user=%s", log_id, hash_user_id(user_id))

    async def upsert_cycle_analysis(
        self, user_id: str, analysis: CycleAnalysisResponse
    ) -> None:
        """Upsert cycle analysis for a user (one row per user).

        Args:
            user_id: ID of the user.
            analysis: Computed cycle analysis data.

        Raises:
            DatabaseError: If the database upsert fails.
        """
        row: dict = {
            "user_id": user_id,
            "average_cycle_length": analysis.average_cycle_length,
            "cycle_variability": analysis.cycle_variability,
            "months_since_last_period": analysis.months_since_last_period,
            "inferred_stage": analysis.inferred_stage,
            "calculated_at": "now()",
        }

        try:
            await (
                self.client.table("cycle_analysis")
                .upsert(row, on_conflict="user_id")
                .execute()
            )
        except Exception as exc:
            logger.error("DB upsert failed for cycle_analysis user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to upsert cycle analysis: {exc}") from exc

    async def get_cycle_analysis(self, user_id: str) -> Optional[CycleAnalysisResponse]:
        """Fetch cycle analysis for a user.

        Args:
            user_id: ID of the user.

        Returns:
            CycleAnalysisResponse or None if no analysis exists.

        Raises:
            DatabaseError: If the database query fails.
        """
        try:
            response = (
                await self.client.table("cycle_analysis")
                .select(
                    "average_cycle_length, cycle_variability, months_since_last_period, "
                    "inferred_stage, calculated_at"
                )
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.error("DB query failed fetching cycle analysis user=%s: %s", hash_user_id(user_id), exc, exc_info=True)
            raise DatabaseError(f"Failed to retrieve cycle analysis: {exc}") from exc

        if not response.data:
            return None
        return CycleAnalysisResponse.model_validate(response.data[0])

    @staticmethod
    def _to_model(row: dict) -> PeriodLogResponse:
        return PeriodLogResponse.model_validate(row)
