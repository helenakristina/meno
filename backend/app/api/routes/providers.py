"""Provider directory search endpoints — no auth required (public data).

Shortlist endpoints require auth (per-user private data).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import CurrentUser, get_providers_repo, get_llm_service
from app.exceptions import DuplicateEntityError
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
from app.repositories.providers_repository import ProvidersRepository
from app.services.llm import LLMService
from app.services.providers import assemble_calling_script_prompts
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


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
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
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
    return await repo.search_providers(
        state=state,
        city=city,
        zip_code=zip_code,
        nams_only=nams_only,
        provider_type=provider_type,
        insurance=insurance,
        page=page,
        page_size=page_size,
    )


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
async def list_states(
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> list[StateCount]:
    """Return states with provider counts sorted by state code.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    return await repo.get_states()


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
async def list_insurance_options(
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> list[str]:
    """Return deduplicated, sorted insurance names from all providers.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    return await repo.get_insurance_options()


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
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
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
        hash_user_id(user_id),
        request.provider_name,
        request.insurance_type,
        request.interested_in_telehealth,
    )

    try:
        script = await llm_service.generate_calling_script(system_prompt, user_prompt)
    except Exception as exc:
        logger.error(
            "LLM call failed for calling script (user=%s provider=%s): %s",
            hash_user_id(user_id),
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
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> list[str]:
    """Return provider_ids in the user's shortlist.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    return await repo.get_shortlist_ids(user_id)


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
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> list[ShortlistEntryWithProvider]:
    """Return all shortlist entries with full provider data joined in.

    Raises:
        HTTPException: 500 for unexpected database failures.
    """
    return await repo.get_shortlist(user_id)


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
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> ShortlistEntry:
    """Add a provider to the user's shortlist.

    Returns 201 with new entry, or lets DuplicateEntityError propagate to 409 handler.
    """
    entry = await repo.add_to_shortlist(user_id, request.provider_id)
    return entry


@router.delete(
    "/shortlist/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove provider from shortlist",
    description="Removes a provider from the current user's shortlist.",
)
async def remove_from_shortlist(
    provider_id: str,
    user_id: CurrentUser,
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> Response:
    """Remove a provider from the user's shortlist.

    Raises:
        HTTPException: 404 if provider is not in the user's shortlist.
        HTTPException: 500 for unexpected database failures.
    """
    await repo.remove_from_shortlist(user_id, provider_id)
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
    repo: Annotated[ProvidersRepository, Depends(get_providers_repo)],
) -> ShortlistEntry:
    """Update status and/or notes for a shortlist entry.

    None values are ignored — only provided fields are updated.
    An empty string for notes clears the notes field in the database.

    Raises:
        HTTPException: 404 if provider is not in the user's shortlist.
        HTTPException: 500 for unexpected database failures.
    """
    return await repo.update_shortlist_entry(
        user_id,
        provider_id,
        status=request.status.value if request.status else None,
        notes=request.notes,
    )
