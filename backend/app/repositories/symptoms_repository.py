"""Data access layer for Symptoms entity.

Handles all Supabase queries for symptom logs and reference data.
Keeps data access logic out of routes and services.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from supabase import AsyncClient

from app.exceptions import DatabaseError, ValidationError
from app.models.symptoms import SymptomDetail, SymptomLogResponse

logger = logging.getLogger(__name__)


class SymptomsRepository:
    """Data access for Symptoms entity.

    Handles all Supabase queries for symptom logs, reference data, and validation.
    Enforces user ownership on all queries.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def validate_ids(self, symptom_ids: list[str]) -> None:
        """Validate that all symptom IDs exist in the symptoms_reference table.

        Deduplicates the input before querying so duplicate IDs in the request
        do not cause a false validation failure.

        Args:
            symptom_ids: List of symptom IDs to validate.

        Raises:
            ValidationError: If any IDs are absent from symptoms_reference.
            DatabaseError: If the reference table query fails.
        """
        if not symptom_ids:
            return

        unique_ids = list(set(symptom_ids))

        try:
            result = (
                await self.client.table("symptoms_reference")
                .select("id")
                .in_("id", unique_ids)
                .execute()
            )
        except Exception as exc:
            logger.error("Failed to query symptoms_reference: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to validate symptom IDs: {exc}") from exc

        if len(result.data) != len(unique_ids):
            valid_ids = {row["id"] for row in result.data}
            invalid_ids = sorted(set(unique_ids) - valid_ids)
            raise ValidationError(f"Invalid symptom IDs: {invalid_ids}")

    async def get_summary(self, user_id: str) -> str:
        """Return the latest cached symptom summary text.

        Fetches the most recently generated cached symptom summary for the user.
        Returns a default message if no summary exists or the query fails.

        Args:
            user_id: ID of the user.

        Returns:
            Cached symptom summary text, or a default message if unavailable.
        """
        try:
            response = (
                await self.client.table("symptom_summary_cache")
                .select("summary_text")
                .eq("user_id", user_id)
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0].get("summary_text") or "No symptom data logged yet."
        except Exception as exc:
            logger.warning("Failed to fetch symptom summary for %s: %s", user_id, exc)
        return "No symptom data logged yet."

    async def create_log(
        self,
        user_id: str,
        symptoms: list[str],
        free_text_entry: str | None = None,
        source: str = "cards",
        logged_at: datetime | None = None,
    ) -> SymptomLogResponse:
        """Create a new symptom log entry for a user.

        Args:
            user_id: Owner of the log.
            symptoms: List of symptom IDs.
            free_text_entry: Optional free-text notes.
            source: How the log was created ("cards", "text", or "both").
            logged_at: Optional timestamp for the log; defaults to NOW() if omitted.

        Returns:
            Created SymptomLogResponse with enriched symptom details.

        Raises:
            ValidationError: If symptom ID validation fails.
            DatabaseError: If the database insert fails.
        """
        # Validate symptom IDs exist
        await self.validate_ids(symptoms)

        row: dict = {
            "user_id": user_id,
            "symptoms": symptoms,
            "free_text_entry": free_text_entry,
            "source": source,
        }
        if logged_at is not None:
            row["logged_at"] = logged_at.isoformat()

        try:
            response = await self.client.table("symptom_logs").insert(row).execute()
        except Exception as exc:
            logger.error(
                "DB insert failed for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to create symptom log: {exc}") from exc

        if not response.data:
            logger.error("Supabase returned no data after insert for user %s", user_id)
            raise DatabaseError("Failed to create symptom log: no data returned")

        created = response.data[0]
        try:
            lookup = await self._fetch_lookup(created.get("symptoms") or [])
        except Exception as exc:
            logger.error(
                "Failed to enrich symptom data for log %s: %s",
                created["id"],
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to create symptom log: {exc}") from exc

        logger.info("Symptom log created: id=%s user=%s", created["id"], user_id)
        return self._enrich_log(created, lookup)

    async def get_logs_with_reference(
        self,
        user_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Fetch raw symptom logs with reference data for stats calculations.

        Returns raw log rows (symptoms field only) and a lookup dict of symptom
        reference data. Used by stats calculation services (frequency, cooccurrence).

        Args:
            user_id: ID of the user.
            start_date: Include logs on or after this date (UTC, ISO 8601).
            end_date: Include logs on or before this date (UTC, ISO 8601).

        Returns:
            Tuple of (list of raw log rows, dict[symptom_id → {id, name, category}]).

        Raises:
            DatabaseError: If the database queries fail.
        """
        try:
            query = self.client.table("symptom_logs").select("symptoms").eq("user_id", user_id)

            if start_date is not None:
                start_dt = datetime(
                    start_date.year,
                    start_date.month,
                    start_date.day,
                    tzinfo=timezone.utc,
                )
                query = query.gte("logged_at", start_dt.isoformat())

            if end_date is not None:
                end_dt = datetime(
                    end_date.year,
                    end_date.month,
                    end_date.day,
                    23,
                    59,
                    59,
                    tzinfo=timezone.utc,
                )
                query = query.lte("logged_at", end_dt.isoformat())

            response = await query.execute()
            rows = response.data or []
        except Exception as exc:
            logger.error(
                "DB query failed fetching logs for stats (user %s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve symptom statistics: {exc}") from exc

        # Extract all unique symptom IDs from logs
        all_ids = list({sid for row in rows for sid in (row.get("symptoms") or [])})

        # If no symptoms found, return empty reference lookup
        if not all_ids:
            return rows, {}

        # Fetch reference data for all symptom IDs found
        try:
            ref_response = (
                await self.client.table("symptoms_reference")
                .select("id, name, category")
                .in_("id", all_ids)
                .execute()
            )
            ref_rows = ref_response.data or []
        except Exception as exc:
            logger.error(
                "DB query failed fetching symptoms_reference for stats (user %s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve symptom statistics: {exc}") from exc

        # Build lookup dict: symptom_id → {id, name, category}
        ref_lookup = {row["id"]: row for row in ref_rows}
        return rows, ref_lookup

    async def get_logs_for_export(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> tuple[list[dict], dict[str, dict]]:
        """Fetch logs with all fields for export (PDF/CSV) with reference data.

        Returns raw log rows (logged_at, symptoms, free_text_entry) ordered
        ascending by logged_at, and a lookup dict of symptom reference data.
        Used by export endpoints for PDF and CSV generation.

        Args:
            user_id: ID of the user.
            start_date: Include logs on or after this date (UTC, ISO 8601).
            end_date: Include logs on or before this date (UTC, ISO 8601).

        Returns:
            Tuple of (list of raw log rows, dict[symptom_id → {id, name, category}]).
            Rows are ordered by logged_at ascending.

        Raises:
            DatabaseError: If the database queries fail.
        """
        try:
            start_dt = datetime(
                start_date.year,
                start_date.month,
                start_date.day,
                tzinfo=timezone.utc,
            )
            end_dt = datetime(
                end_date.year,
                end_date.month,
                end_date.day,
                23,
                59,
                59,
                tzinfo=timezone.utc,
            )
            response = (
                await self.client.table("symptom_logs")
                .select("logged_at, symptoms, free_text_entry")
                .eq("user_id", user_id)
                .gte("logged_at", start_dt.isoformat())
                .lte("logged_at", end_dt.isoformat())
                .order("logged_at", desc=False)
                .execute()
            )
            rows = response.data or []
        except Exception as exc:
            logger.error(
                "DB query failed fetching logs for export (user %s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve symptom logs: {exc}") from exc

        # Extract all unique symptom IDs from logs
        all_ids = list({sid for row in rows for sid in (row.get("symptoms") or [])})

        # If no symptoms found, return empty reference lookup
        if not all_ids:
            return rows, {}

        # Fetch reference data for all symptom IDs found
        try:
            ref_response = (
                await self.client.table("symptoms_reference")
                .select("id, name, category")
                .in_("id", all_ids)
                .execute()
            )
            ref_rows = ref_response.data or []
        except Exception as exc:
            logger.error(
                "DB query failed fetching symptoms_reference for export (user %s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve symptom data: {exc}") from exc

        # Build lookup dict: symptom_id → {id, name, category}
        ref_lookup = {row["id"]: row for row in ref_rows}
        return rows, ref_lookup

    async def get_logs(
        self,
        user_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> tuple[list[SymptomLogResponse], int]:
        """Fetch symptom logs for a user with optional date filtering.

        Date filters are inclusive and cover the full UTC day (00:00:00–23:59:59).
        Results are ordered newest-first.

        Args:
            user_id: ID of the user.
            start_date: Include logs on or after this date (UTC, ISO 8601).
            end_date: Include logs on or before this date (UTC, ISO 8601).
            limit: Maximum number of logs to return (1–100).

        Returns:
            Tuple of (enriched log list, total count).

        Raises:
            DatabaseError: If the database query fails.
        """
        rows: list[dict] = []
        lookup: dict[str, SymptomDetail] = {}

        try:
            query = self.client.table("symptom_logs").select("*").eq("user_id", user_id)

            if start_date is not None:
                start_dt = datetime(
                    start_date.year,
                    start_date.month,
                    start_date.day,
                    tzinfo=timezone.utc,
                )
                query = query.gte("logged_at", start_dt.isoformat())

            if end_date is not None:
                end_dt = datetime(
                    end_date.year,
                    end_date.month,
                    end_date.day,
                    23,
                    59,
                    59,
                    tzinfo=timezone.utc,
                )
                query = query.lte("logged_at", end_dt.isoformat())

            query = query.order("logged_at", desc=True).limit(limit)
            response = await query.execute()

            rows = response.data or []
            unique_ids = list(
                {sid for row in rows for sid in (row.get("symptoms") or [])}
            )
            lookup = await self._fetch_lookup(unique_ids)

        except Exception as exc:
            logger.error(
                "DB query failed for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve symptom logs: {exc}") from exc

        logs = [self._enrich_log(row, lookup) for row in rows]
        logger.info("Retrieved %d symptom logs for user %s", len(logs), user_id)
        return logs, len(logs)

    async def _fetch_lookup(
        self, symptom_ids: list[str]
    ) -> dict[str, SymptomDetail]:
        """Query symptoms_reference for the given IDs and return an id → SymptomDetail map.

        Missing IDs are silently omitted from the result; callers handle the
        fallback so we avoid tight coupling between this helper and logging policy.

        Args:
            symptom_ids: List of symptom IDs to fetch.

        Returns:
            Mapping of symptom ID to SymptomDetail.
        """
        if not symptom_ids:
            return {}

        response = (
            await self.client.table("symptoms_reference")
            .select("id, name, category")
            .in_("id", symptom_ids)
            .execute()
        )
        return {
            row["id"]: SymptomDetail(
                id=row["id"], name=row["name"], category=row["category"]
            )
            for row in (response.data or [])
        }

    @staticmethod
    def _enrich_log(row: dict, lookup: dict[str, SymptomDetail]) -> SymptomLogResponse:
        """Build a SymptomLogResponse, resolving symptom IDs to SymptomDetail objects.

        Any ID not present in the lookup is a data-integrity anomaly: a warning is
        logged and a fallback SymptomDetail with name=id and category="unknown" is
        used so the log is never silently dropped.

        Args:
            row: Raw log row from database.
            lookup: Mapping of symptom ID to SymptomDetail.

        Returns:
            Enriched SymptomLogResponse with resolved symptom details.
        """
        enriched: list[SymptomDetail] = []
        for sid in row.get("symptoms") or []:
            if sid in lookup:
                enriched.append(lookup[sid])
            else:
                logger.warning(
                    "Symptom ID %s not found in symptoms_reference (data integrity issue)",
                    sid,
                )
                enriched.append(SymptomDetail(id=sid, name=sid, category="unknown"))

        return SymptomLogResponse(
            id=row["id"],
            user_id=row["user_id"],
            logged_at=row["logged_at"],
            symptoms=enriched,
            free_text_entry=row.get("free_text_entry"),
            source=row["source"],
        )
