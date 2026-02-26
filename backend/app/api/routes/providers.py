"""Provider directory search endpoints — no auth required (public data).

Shortlist endpoints require auth (per-user private data).
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from supabase import AsyncClient

from app.api.dependencies import CurrentUser
from app.core.supabase import get_client
from app.models.providers import (
    AddToShortlistRequest,
    CallingScriptRequest,
    CallingScriptResponse,
    ProviderSearchResponse,
    ShortlistEntry,
    ShortlistEntryWithProvider,
    StateCount,
    UpdateShortlistRequest,
)
from app.services.llm import generate_calling_script
from app.services.providers import (
    aggregate_states,
    assemble_calling_script_prompts,
    collect_insurance_options,
    filter_and_paginate,
    to_provider_card,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])

SupabaseClient = Annotated[AsyncClient, Depends(get_client)]

# Upper bound on rows fetched per search — safely covers any single state's
# provider count given the current dataset (~5,500 providers total, ~50 states).
_MAX_FETCH = 1000

# PostgREST returns at most 1000 rows per request by default. This helper
# paginates transparently so callers get every row regardless of dataset size.
_PAGE_SIZE = 1000


async def _fetch_all(client: AsyncClient, table: str, columns: str) -> list[dict]:
    """Paginate through all rows in a table, returning every matching row.

    Uses PostgREST range-based pagination (.range(from, to)) to work within
    the 1,000-row-per-request default limit of the Supabase PostgREST API.
    """
    all_rows: list[dict] = []
    offset = 0
    while True:
        response = (
            await client.table(table)
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


# ---------------------------------------------------------------------------
# GET /api/providers/search
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=ProviderSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search provider directory",
    description=(
        "Search NAMS-certified providers by state, city, or zip code with "
        "optional filters. State is the primary location mechanism for V1. "
        "Provide either 'state' or 'zip_code' (or both)."
    ),
)
async def search_providers(
    client: SupabaseClient,
    state: str | None = Query(
        default=None,
        description="2-letter state code (required if no zip_code)",
    ),
    city: str | None = Query(
        default=None,
        description="City name — case-insensitive, partial match supported",
    ),
    zip_code: str | None = Query(
        default=None,
        description="ZIP code — state is inferred from the providers table",
    ),
    nams_only: bool = Query(
        default=True,
        description="Limit to NAMS-certified providers",
    ),
    provider_type: str | None = Query(
        default=None,
        description="ob_gyn | internal_medicine | np_pa | integrative_medicine | other",
    ),
    insurance: str | None = Query(
        default=None,
        description=(
            "Insurance name — case-insensitive substring match against each "
            "provider's accepted insurances"
        ),
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        default=20, ge=1, le=50, description="Results per page (max 50)"
    ),
) -> ProviderSearchResponse:
    """Search providers by location with optional filters.

    Either 'state' or 'zip_code' must be supplied. When zip_code is given
    without a state, the state is looked up from the providers table (no
    external geocoding API). City and insurance filtering are applied in
    Python after the state-level DB fetch.

    Raises:
        HTTPException: 400 if neither state nor zip_code is provided.
        HTTPException: 400 if zip_code is supplied but not found in the table.
        HTTPException: 422 if page_size exceeds 50.
        HTTPException: 500 for unexpected database failures.
    """
    if not state and not zip_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'state' or 'zip_code' is required",
        )

    effective_state = state.upper().strip() if state else None

    # If only zip_code is provided, infer the state from our own providers table.
    if zip_code and not effective_state:
        try:
            zip_response = (
                await client.table("providers")
                .select("state")
                .eq("zip_code", zip_code.strip())
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.error(
                "DB error looking up zip_code %s: %s", zip_code, exc, exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to look up zip code",
            )

        if not zip_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No providers found for zip_code '{zip_code}'",
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
        insurance,
        page,
        page_size,
    )

    try:
        query = (
            client.table("providers")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search providers",
        )

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


# ---------------------------------------------------------------------------
# GET /api/providers/states
# ---------------------------------------------------------------------------


@router.get(
    "/states",
    response_model=list[StateCount],
    status_code=status.HTTP_200_OK,
    summary="List states with provider counts",
    description=(
        "Returns all US states that have providers, with count per state, "
        "sorted alphabetically. Used to populate the state dropdown."
    ),
)
async def list_states(client: SupabaseClient) -> list[StateCount]:
    """Return states with provider counts sorted by state code.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    try:
        rows = await _fetch_all(client, "providers", "state")
    except Exception as exc:
        logger.error(
            "DB query failed fetching provider states: %s", exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve state list",
        )

    aggregated = aggregate_states(rows)
    logger.info("States endpoint: returned %d states", len(aggregated))
    return [StateCount(**item) for item in aggregated]


# ---------------------------------------------------------------------------
# GET /api/providers/insurance-options
# ---------------------------------------------------------------------------


@router.get(
    "/insurance-options",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List available insurance options",
    description=(
        "Returns all distinct insurance values across all providers, "
        "sorted alphabetically. Used to populate the insurance filter dropdown."
    ),
)
async def list_insurance_options(client: SupabaseClient) -> list[str]:
    """Return deduplicated, sorted insurance names from all providers.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    try:
        rows = await _fetch_all(client, "providers", "insurance_accepted")
    except Exception as exc:
        logger.error(
            "DB query failed fetching insurance options: %s", exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insurance options",
        )

    options = collect_insurance_options(rows)
    logger.info(
        "Insurance options endpoint: returned %d distinct values", len(options)
    )
    return options


# ---------------------------------------------------------------------------
# POST /api/providers/calling-script
# ---------------------------------------------------------------------------


@router.post(
    "/calling-script",
    response_model=CallingScriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate provider calling script",
    description=(
        "Generate a short, personalized script for calling a provider's office. "
        "Tailored to insurance type and telehealth preference. "
        "Only insurance context is sent to the LLM — no user PII or symptom data."
    ),
)
async def generate_provider_calling_script(
    request: CallingScriptRequest,
    user_id: CurrentUser,
) -> CallingScriptResponse:
    """Generate a calling script via the LLM.

    Prompt assembly (pure, no side effects) happens in the service layer.
    The LLM call is made here so errors surface as HTTP 500 with proper logging.
    User ID is captured from the auth token for logging only — never sent to the LLM.

    Raises:
        HTTPException: 400 if provider_name is blank.
        HTTPException: 500 if the LLM call fails.
    """
    if not request.provider_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider_name is required",
        )

    system_prompt, user_prompt = assemble_calling_script_prompts(request)

    logger.info(
        "Generating calling script: user=%s provider=%s insurance=%s telehealth=%s",
        user_id,
        request.provider_name,
        request.insurance_type,
        request.interested_in_telehealth,
    )

    try:
        script = await generate_calling_script(system_prompt, user_prompt)
    except Exception as exc:
        logger.error(
            "LLM call failed for calling script (user=%s provider=%s): %s",
            user_id,
            request.provider_name,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate calling script",
        )

    return CallingScriptResponse(script=script, provider_name=request.provider_name)


# ---------------------------------------------------------------------------
# Shortlist / Call Tracker endpoints
# NOTE: /shortlist/ids must be registered before /shortlist/{provider_id}
# so the literal path "ids" is not swallowed by the parameterized route.
# ---------------------------------------------------------------------------


@router.get(
    "/shortlist/ids",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="Get shortlisted provider IDs",
    description=(
        "Returns the list of provider_ids the current user has saved. "
        "Lightweight — used by the search page to show bookmark state on cards "
        "without fetching full shortlist data."
    ),
)
async def get_shortlist_ids(
    user_id: CurrentUser,
    client: SupabaseClient,
) -> list[str]:
    """Return provider_ids in the user's shortlist.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    try:
        resp = (
            await client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shortlist",
        )

    return [row["provider_id"] for row in (resp.data or [])]


@router.get(
    "/shortlist",
    response_model=list[ShortlistEntryWithProvider],
    status_code=status.HTTP_200_OK,
    summary="Get user shortlist with provider details",
    description=(
        "Returns all shortlisted providers for the current user, "
        "each entry including the full provider card data. "
        "Ordered by added_at descending (most recently added first)."
    ),
)
async def get_shortlist(
    user_id: CurrentUser,
    client: SupabaseClient,
) -> list[ShortlistEntryWithProvider]:
    """Return all shortlist entries with full provider data joined in.

    Makes two DB queries: one for shortlist entries, one for provider rows.
    Joining in Python avoids complex PostgREST syntax and keeps the route testable.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    try:
        entries_resp = (
            await client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shortlist",
        )

    if not entries:
        return []

    provider_ids = [e["provider_id"] for e in entries]

    try:
        providers_resp = (
            await client.table("providers")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve shortlist",
        )

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


@router.post(
    "/shortlist",
    status_code=status.HTTP_201_CREATED,
    summary="Add provider to shortlist",
    description=(
        "Adds a provider to the current user's shortlist with default status 'to_call'. "
        "Returns the created entry (201) or the existing entry with HTTP 409 if already saved."
    ),
)
async def add_to_shortlist(
    request: AddToShortlistRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> ShortlistEntry:
    """Add a provider to the user's shortlist.

    Returns 409 with the existing ShortlistEntry if the provider is already saved,
    so the caller can treat it as a no-op rather than an error.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    try:
        existing_resp = (
            await client.table("provider_shortlist")
            .select("*")
            .eq("user_id", user_id)
            .eq("provider_id", request.provider_id)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB query failed checking existing shortlist entry (user=%s provider=%s): %s",
            user_id,
            request.provider_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add provider to shortlist",
        )

    if existing_resp.data:
        # Already in shortlist — return existing entry with 409 so caller can distinguish
        logger.info(
            "Shortlist add: already exists (user=%s provider=%s)",
            user_id,
            request.provider_id,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=existing_resp.data[0],
        )

    try:
        insert_resp = (
            await client.table("provider_shortlist")
            .insert({"user_id": user_id, "provider_id": request.provider_id, "status": "to_call"})
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB insert failed for shortlist (user=%s provider=%s): %s",
            user_id,
            request.provider_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add provider to shortlist",
        )

    logger.info("Shortlist add: success (user=%s provider=%s)", user_id, request.provider_id)
    return ShortlistEntry(**insert_resp.data[0])


@router.delete(
    "/shortlist/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove provider from shortlist",
    description="Removes a provider from the current user's shortlist.",
)
async def remove_from_shortlist(
    provider_id: str,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> Response:
    """Remove a provider from the user's shortlist.

    Raises:
        HTTPException: 404 if provider is not in the user's shortlist.
        HTTPException: 500 for unexpected database failures.
    """
    try:
        existing_resp = (
            await client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove provider from shortlist",
        )

    if not existing_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not in shortlist",
        )

    try:
        await (
            client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove provider from shortlist",
        )

    logger.info("Shortlist remove: success (user=%s provider=%s)", user_id, provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/shortlist/{provider_id}",
    response_model=ShortlistEntry,
    status_code=status.HTTP_200_OK,
    summary="Update shortlist entry",
    description=(
        "Updates status and/or notes for a shortlisted provider. "
        "Pass only the fields you want to change. "
        "Set notes to empty string to clear notes."
    ),
)
async def update_shortlist_entry(
    provider_id: str,
    request: UpdateShortlistRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
) -> ShortlistEntry:
    """Update status and/or notes for a shortlist entry.

    None values are ignored — only provided fields are updated.
    An empty string for notes clears the notes field in the database.

    Raises:
        HTTPException: 404 if provider is not in the user's shortlist.
        HTTPException: 500 for unexpected database failures.
    """
    try:
        existing_resp = (
            await client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update shortlist entry",
        )

    if not existing_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not in shortlist",
        )

    updates: dict = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    if request.status is not None:
        updates["status"] = request.status.value
    if request.notes is not None:
        # Empty string → null in DB (clear notes)
        updates["notes"] = request.notes.strip() or None

    try:
        update_resp = (
            await client.table("provider_shortlist")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update shortlist entry",
        )

    logger.info(
        "Shortlist update: success (user=%s provider=%s status=%s)",
        user_id,
        provider_id,
        request.status,
    )
    return ShortlistEntry(**update_resp.data[0])
