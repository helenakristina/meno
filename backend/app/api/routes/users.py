import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from app.api.dependencies import CurrentUser, get_user_repo
from app.core.supabase import get_client
from app.models.users import (
    InsurancePreference,
    InsurancePreferenceUpdate,
    OnboardingRequest,
    UserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.repositories.user_repository import UserRepository
from app.utils.dates import validate_date_of_birth
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


SupabaseClient = Annotated[AsyncClient, Depends(get_client)]


# ---------------------------------------------------------------------------
# POST /api/users/onboarding
# ---------------------------------------------------------------------------


@router.post(
    "/onboarding",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete user onboarding",
    description=(
        "Create a user profile in public.users after Supabase Auth signup. "
        "Called exactly once per user. Email is sourced from auth.users, not the request."
    ),
)
async def onboarding(
    payload: OnboardingRequest,
    user_id: CurrentUser,
    client: SupabaseClient,
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserResponse:
    """Create a user profile for the authenticated user.

    The user_id and email are derived from the validated JWT — callers cannot
    create profiles on behalf of another user. Supabase RLS enforces this at
    the database level as a second layer of defense.

    Raises:
        HTTPException: 400 if date_of_birth is in the future or user is under 18.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 409 if a profile already exists for this user.
        HTTPException: 500 if the database insert or auth lookup fails.
    """
    try:
        validate_date_of_birth(payload.date_of_birth)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Get email from auth.users — trust the JWT, not the request body
    try:
        auth_response = await client.auth.admin.get_user_by_id(user_id)
        email = auth_response.user.email
    except Exception as exc:
        logger.error(
            "Auth lookup failed for user %s: %s", hash_user_id(user_id), exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding",
        )

    # Create user profile via repository (handles duplicate checks and insert)
    created = await user_repo.create(
        user_id=user_id,
        email=email,
        data={
            "date_of_birth": payload.date_of_birth.isoformat(),
            "journey_stage": payload.journey_stage,
            "onboarding_completed": True,
        },
    )

    logger.info("User profile created: user=%s", hash_user_id(user_id))
    return UserResponse.model_validate(created)


# ---------------------------------------------------------------------------
# GET /api/users/insurance-preference
# ---------------------------------------------------------------------------


@router.get(
    "/insurance-preference",
    response_model=InsurancePreference,
    status_code=status.HTTP_200_OK,
    summary="Get insurance preference",
    description="Return the user's saved insurance type and plan name, or null values if not set.",
)
async def get_insurance_preference(
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
) -> InsurancePreference:
    """Fetch insurance_type and insurance_plan_name from the user's profile row.

    Returns null values rather than 404 when the profile exists but the
    columns are unset — the frontend treats null as "not yet saved".

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 500 for unexpected database failures.
    """
    profile = await user_repo.get(user_id)

    if not profile:
        return InsurancePreference(insurance_type=None, insurance_plan_name=None)

    return InsurancePreference(
        insurance_type=profile.insurance_type,
        insurance_plan_name=profile.insurance_plan_name,
    )


# ---------------------------------------------------------------------------
# PATCH /api/users/insurance-preference
# ---------------------------------------------------------------------------


@router.patch(
    "/insurance-preference",
    response_model=InsurancePreference,
    status_code=status.HTTP_200_OK,
    summary="Update insurance preference",
    description="Persist the user's insurance type and optional plan name to their profile.",
)
async def update_insurance_preference(
    payload: InsurancePreferenceUpdate,
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
) -> InsurancePreference:
    """Write insurance_type and insurance_plan_name to the user's profile row.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if no user profile exists for the authenticated user.
        HTTPException: 422 if insurance_type is not a valid enum value.
        HTTPException: 500 for unexpected database failures.
    """
    updated = await user_repo.update_profile(
        user_id,
        {
            "insurance_type": payload.insurance_type.value,
            "insurance_plan_name": payload.insurance_plan_name,
        },
    )

    logger.info(
        "Insurance preference updated: user=%s type=%s", hash_user_id(user_id), payload.insurance_type
    )
    return InsurancePreference(
        insurance_type=updated.insurance_type,
        insurance_plan_name=updated.insurance_plan_name,
    )


# ---------------------------------------------------------------------------
# GET /api/users/settings
# ---------------------------------------------------------------------------


@router.get(
    "/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user settings",
    description="Return period_tracking_enabled, has_uterus, and journey_stage for the authenticated user.",
)
async def get_settings(
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserSettingsResponse:
    """Fetch period tracking preferences and journey stage.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if user profile not found.
        HTTPException: 500 for unexpected failures.
    """
    return await user_repo.get_settings(user_id)


# ---------------------------------------------------------------------------
# PATCH /api/users/settings
# ---------------------------------------------------------------------------


@router.patch(
    "/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user settings",
    description=(
        "Update period_tracking_enabled, has_uterus, and/or journey_stage. "
        "Setting has_uterus=false automatically disables period tracking."
    ),
)
async def update_settings(
    payload: UserSettingsUpdate,
    user_id: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserSettingsResponse:
    """Update user settings. All fields are optional; only provided fields are updated.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if user profile not found.
        HTTPException: 422 if journey_stage is invalid.
        HTTPException: 500 for unexpected failures.
    """
    # Business rule: no uterus → period tracking must be off
    if "has_uterus" in payload.model_fields_set and payload.has_uterus is False:
        fields = {k: getattr(payload, k) for k in payload.model_fields_set}
        fields["period_tracking_enabled"] = False
        payload = UserSettingsUpdate.model_validate(fields)

    updated = await user_repo.update_settings(user_id, payload)
    logger.info("User settings updated: user=%s", hash_user_id(user_id))
    return updated
