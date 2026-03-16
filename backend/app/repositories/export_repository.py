"""Data access layer for Export entity.

Records export events for audit trail and retrieves export history.
"""

import logging
from datetime import date

from supabase import AsyncClient

from app.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class ExportRepository:
    """Data access for export records.

    Writes to and reads from the exports table (immutable audit trail).
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def record_export(
        self,
        user_id: str,
        export_type: str,
        date_range_start: date,
        date_range_end: date,
    ) -> dict:
        """Record an export event in the database.

        Args:
            user_id: Authenticated user ID.
            export_type: Export format ('pdf' or 'csv').
            date_range_start: Start of the exported date range.
            date_range_end: End of the exported date range.

        Returns:
            The inserted record as a dict.

        Raises:
            DatabaseError: If the insert fails.
        """
        try:
            result = (
                await self.client.table("exports")
                .insert(
                    {
                        "user_id": user_id,
                        "export_type": export_type,
                        "date_range_start": date_range_start.isoformat(),
                        "date_range_end": date_range_end.isoformat(),
                    }
                )
                .execute()
            )
            record = result.data[0] if result.data else {}
            logger.info(
                "Export recorded: type=%s range=%s–%s",
                export_type,
                date_range_start,
                date_range_end,
            )
            return record
        except Exception as exc:
            logger.error(
                "Failed to record export: type=%s error=%s",
                export_type,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to record export: {exc}") from exc

    async def get_export_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get a user's export history, most recent first.

        Args:
            user_id: Authenticated user ID.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            Tuple of (records list, total count).

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            result = (
                await self.client.table("exports")
                .select("*", count="exact")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .offset(offset)
                .execute()
            )
            records = result.data or []
            total = result.count or 0
            return records, total
        except Exception as exc:
            logger.error(
                "Failed to get export history: error=%s",
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to get export history: {exc}") from exc
