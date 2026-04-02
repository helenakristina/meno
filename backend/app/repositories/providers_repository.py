"""Data access layer for Providers entity.

Handles all Supabase queries for provider search, states, insurance options, and shortlist management.
Keeps data access logic out of routes and services.
"""

import logging
from datetime import datetime, timezone

from supabase import AsyncClient

from app.exceptions import (
    DatabaseError,
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)

from app.models.providers import (
    ProviderSearchResponse,
    ShortlistEntry,
    ShortlistEntryWithProvider,
    StateCount,
)
from app.services.providers import (
    aggregate_states,
    collect_insurance_options,
    filter_and_paginate,
    to_provider_card,
)

logger = logging.getLogger(__name__)

# Upper bound on rows fetched per search — safely covers any single state's
# provider count given the current dataset (~5,500 providers total, ~50 states).
_MAX_FETCH = 1000

# PostgREST returns at most 1000 rows per request by default. This helper
# paginates transparently so callers get every row regardless of dataset size.
_PAGE_SIZE = 1000


class ProvidersRepository:
    """Data access for Providers entity.

    Handles all Supabase queries for provider search, reference data,
    and shortlist management. Enforces user ownership on shortlist operations.
    """

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for database access.
        """
        self.client = client

    async def search_providers(
        self,
        state: str | None = None,
        city: str | None = None,
        zip_code: str | None = None,
        nams_only: bool = True,
        provider_type: str | None = None,
        insurance: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProviderSearchResponse:
        """Search providers by location with optional filters.

        Either 'state' or 'zip_code' must be supplied. When zip_code is given
        without a state, the state is looked up from the providers table (no
        external geocoding API). City and insurance filtering are applied in
        Python after the state-level DB fetch.

        Args:
            state: 2-letter state code (optional if zip_code provided).
            city: City name — case-insensitive, partial match supported.
            zip_code: ZIP code — state is inferred from providers table if state is None.
            nams_only: Limit to NAMS-certified providers (default True).
            provider_type: Filter by provider type (ob_gyn, internal_medicine, etc.).
            insurance: Filter by insurance name (case-insensitive substring match).
            page: Page number (1-indexed, default 1).
            page_size: Results per page (default 20, max 50).

        Returns:
            ProviderSearchResponse with paginated results and total counts.

        Raises:
            ValidationError: If neither state nor zip_code is provided.
            EntityNotFoundError: If zip_code is supplied but not found in the table.
            DatabaseError: For unexpected database failures.
        """
        if not state and not zip_code:
            raise ValidationError("Either 'state' or 'zip_code' is required")

        effective_state = state.upper().strip() if state else None

        # If only zip_code is provided, infer the state from our own providers table.
        if zip_code and not effective_state:
            try:
                zip_response = (
                    await self.client.table("providers")
                    .select("state")
                    .eq("zip_code", zip_code.strip())
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                logger.error(
                    "DB error looking up zip_code %s: %s", zip_code, exc, exc_info=True
                )
                raise DatabaseError(f"Failed to look up zip code: {exc}") from exc

            if not zip_response.data:
                raise EntityNotFoundError(
                    f"No providers found for zip_code '{zip_code}'"
                )
            effective_state = zip_response.data[0]["state"]

        logger.info(
            "Provider search: state=%s city=%s zip=%s nams_only=%s "
            "provider_type=%s insurance=%s page=%d page_size=%d",
            effective_state,
            city,
            zip_code,
            nams_only,
            provider_type,
            page,
            page_size,
        )

        try:
            query = (
                self.client.table("providers")
                .select("*")
                .eq("state", effective_state)
                .limit(_MAX_FETCH)
            )
            if nams_only:
                query = query.eq("nams_certified", True)
            if provider_type:
                query = query.eq("provider_type", provider_type)
            response = await query.execute()
            rows = response.data or []
        except Exception as exc:
            logger.error(
                "DB query failed for provider search (state=%s): %s",
                effective_state,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to search providers: {exc}") from exc

        result = filter_and_paginate(
            rows, city=city, insurance=insurance, page=page, page_size=page_size
        )
        logger.info(
            "Provider search complete: state=%s total=%d page=%d/%d",
            effective_state,
            result.total,
            result.page,
            result.total_pages,
        )
        return result

    async def get_states(self) -> list[StateCount]:
        """Return states with provider counts sorted by state code.

        Returns:
            List of StateCount objects with state code and provider count.

        Raises:
            DatabaseError: For unexpected database failures.
        """
        try:
            rows = await self._fetch_all("providers", "state")
        except Exception as exc:
            logger.error(
                "DB query failed fetching provider states: %s", exc, exc_info=True
            )
            raise DatabaseError(f"Failed to retrieve state list: {exc}") from exc

        aggregated = aggregate_states(rows)
        logger.info("States endpoint: returned %d states", len(aggregated))
        return [StateCount(**item) for item in aggregated]

    async def get_insurance_options(self) -> list[str]:
        """Return deduplicated, sorted insurance names from all providers.

        Returns:
            List of normalized insurance option strings sorted alphabetically.

        Raises:
            DatabaseError: For unexpected database failures.
        """
        try:
            rows = await self._fetch_all("providers", "insurance_accepted")
        except Exception as exc:
            logger.error(
                "DB query failed fetching insurance options: %s", exc, exc_info=True
            )
            raise DatabaseError(f"Failed to retrieve insurance options: {exc}") from exc

        options = collect_insurance_options(rows)
        logger.info(
            "Insurance options endpoint: returned %d distinct values", len(options)
        )
        return options

    async def get_shortlist(self, user_id: str) -> list[ShortlistEntryWithProvider]:
        """Return all shortlist entries with full provider data joined in.

        Makes two DB queries: one for shortlist entries, one for provider rows.
        Joining in Python avoids complex PostgREST syntax and keeps the route testable.

        Args:
            user_id: ID of the user.

        Returns:
            List of ShortlistEntryWithProvider (shortlist entry + full provider card).

        Raises:
            DatabaseError: For unexpected database failures.
        """
        try:
            entries_resp = (
                await self.client.table("provider_shortlist")
                .select("*")
                .eq("user_id", user_id)
                .order("added_at", desc=True)
                .execute()
            )
            entries = entries_resp.data or []
        except Exception as exc:
            logger.error(
                "DB query failed fetching shortlist (user=%s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve shortlist: {exc}") from exc

        if not entries:
            return []

        provider_ids = [e["provider_id"] for e in entries]

        try:
            providers_resp = (
                await self.client.table("providers")
                .select("*")
                .in_("id", provider_ids)
                .execute()
            )
            providers_by_id = {p["id"]: p for p in (providers_resp.data or [])}
        except Exception as exc:
            logger.error(
                "DB query failed fetching providers for shortlist (user=%s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve shortlist: {exc}") from exc

        result = []
        for entry in entries:
            provider_row = providers_by_id.get(entry["provider_id"])
            if provider_row:
                result.append(
                    ShortlistEntryWithProvider(
                        **{k: v for k, v in entry.items()},
                        provider=to_provider_card(provider_row),
                    )
                )

        logger.info("Shortlist fetch: user=%s entries=%d", user_id, len(result))
        return result

    async def get_shortlist_ids(self, user_id: str) -> list[str]:
        """Return provider_ids in the user's shortlist.

        Returns:
            List of provider IDs (used to show bookmark state on search cards).

        Raises:
            DatabaseError: For unexpected database failures.
        """
        try:
            resp = (
                await self.client.table("provider_shortlist")
                .select("provider_id")
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed fetching shortlist ids (user=%s): %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to retrieve shortlist: {exc}") from exc

        return [row["provider_id"] for row in (resp.data or [])]

    async def add_to_shortlist(self, user_id: str, provider_id: str) -> ShortlistEntry:
        """Add a provider to the user's shortlist.

        Args:
            user_id: ID of the user.
            provider_id: ID of the provider to add.

        Returns:
            Created ShortlistEntry.

        Raises:
            DuplicateEntityError: If provider is already in shortlist.
            DatabaseError: For unexpected database failures.
        """
        try:
            existing_resp = (
                await self.client.table("provider_shortlist")
                .select("*")
                .eq("user_id", user_id)
                .eq("provider_id", provider_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed checking existing shortlist entry (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to add provider to shortlist: {exc}") from exc

        if existing_resp.data:
            logger.info(
                "Shortlist add: already exists (user=%s provider=%s)",
                user_id,
                provider_id,
            )
            raise DuplicateEntityError("Provider already in shortlist")

        try:
            insert_resp = (
                await self.client.table("provider_shortlist")
                .insert(
                    {
                        "user_id": user_id,
                        "provider_id": provider_id,
                        "status": "to_call",
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB insert failed for shortlist (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to add provider to shortlist: {exc}") from exc

        logger.info(
            "Shortlist add: success (user=%s provider=%s)", user_id, provider_id
        )
        return ShortlistEntry(**insert_resp.data[0])

    async def remove_from_shortlist(self, user_id: str, provider_id: str) -> None:
        """Remove a provider from the user's shortlist.

        Args:
            user_id: ID of the user.
            provider_id: ID of the provider to remove.

        Raises:
            EntityNotFoundError: If provider is not in the user's shortlist.
            DatabaseError: For unexpected database failures.
        """
        try:
            existing_resp = (
                await self.client.table("provider_shortlist")
                .select("id")
                .eq("user_id", user_id)
                .eq("provider_id", provider_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed checking shortlist entry (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(
                f"Failed to remove provider from shortlist: {exc}"
            ) from exc

        if not existing_resp.data:
            raise EntityNotFoundError("Provider not in shortlist")

        try:
            await (
                self.client.table("provider_shortlist")
                .delete()
                .eq("user_id", user_id)
                .eq("provider_id", provider_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB delete failed for shortlist (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(
                f"Failed to remove provider from shortlist: {exc}"
            ) from exc

        logger.info(
            "Shortlist remove: success (user=%s provider=%s)", user_id, provider_id
        )

    async def update_shortlist_entry(
        self,
        user_id: str,
        provider_id: str,
        status: str | None = None,
        notes: str | None = None,
    ) -> ShortlistEntry:
        """Update status and/or notes for a shortlist entry.

        None values are ignored — only provided fields are updated.
        An empty string for notes clears the notes field in the database.

        Args:
            user_id: ID of the user.
            provider_id: ID of the provider.
            status: New status value (optional).
            notes: New notes value, or empty string to clear (optional).

        Returns:
            Updated ShortlistEntry.

        Raises:
            EntityNotFoundError: If provider is not in the user's shortlist.
            DatabaseError: For unexpected database failures.
        """
        try:
            existing_resp = (
                await self.client.table("provider_shortlist")
                .select("*")
                .eq("user_id", user_id)
                .eq("provider_id", provider_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB query failed checking shortlist entry (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to update shortlist entry: {exc}") from exc

        if not existing_resp.data:
            raise EntityNotFoundError("Provider not in shortlist")

        updates: dict = {
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if status is not None:
            updates["status"] = status
        if notes is not None:
            # Empty string → null in DB (clear notes)
            updates["notes"] = notes.strip() or None

        try:
            update_resp = (
                await self.client.table("provider_shortlist")
                .update(updates)
                .eq("user_id", user_id)
                .eq("provider_id", provider_id)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB update failed for shortlist (user=%s provider=%s): %s",
                user_id,
                provider_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to update shortlist entry: {exc}") from exc

        logger.info(
            "Shortlist update: success (user=%s provider=%s)",
            user_id,
            provider_id,
        )
        return ShortlistEntry(**update_resp.data[0])

    async def _fetch_all(self, table: str, columns: str) -> list[dict]:
        """Paginate through all rows in a table, returning every matching row.

        Uses PostgREST range-based pagination (.range(from, to)) to work within
        the 1,000-row-per-request default limit of the Supabase PostgREST API.

        Args:
            table: Name of the table to query.
            columns: Comma-separated column names to select.

        Returns:
            List of all rows matching the query.

        Raises:
            Exception: If database query fails (caller should handle).
        """
        all_rows: list[dict] = []
        offset = 0
        while True:
            response = (
                await self.client.table(table)
                .select(columns)
                .range(offset, offset + _PAGE_SIZE - 1)
                .execute()
            )
            batch = response.data or []
            all_rows.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return all_rows
