import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from app.api.dependencies import CurrentUser, get_user_repo
from app.core.supabase import get_client
from app.models.users import InsurancePreference, InsurancePreferenceUpdate, OnboardingRequest, UserResponse
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


SupabaseClient = Annotated[AsyncClient, Depends(get_client)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_date_of_birth(dob: date) -> None:
    """Raise 400 if date_of_birth is in the future or user is under 18."""
    today = date.today()
    if dob >= today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_of_birth must be in the past",
        )
    # Accurately accounts for whether the birthday has occurred yet this year
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be at least 18 years old",
        )


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
    _validate_date_of_birth(payload.date_of_birth)

    # Get email from auth.users — trust the JWT, not the request body
    try:
        auth_response = await client.auth.admin.get_user_by_id(user_id)
        email = auth_response.user.email
    except Exception as exc:
        logger.error(
            "Auth lookup failed for user %s: %s", user_id, exc, exc_info=True
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

    logger.info("User profile created: id=%s email=%s", user_id, email)
    return UserResponse(**created)


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
        insurance_type=profile.get("insurance_type"),
        insurance_plan_name=profile.get("insurance_plan_name"),
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
        "Insurance preference updated: user=%s type=%s", user_id, payload.insurance_type
    )
    return InsurancePreference(
        insurance_type=updated.get("insurance_type"),
        insurance_plan_name=updated.get("insurance_plan_name"),
    )
