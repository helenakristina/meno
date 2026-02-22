import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from app.api.dependencies import CurrentUser
from app.core.supabase import get_client
from app.models.users import InsurancePreference, InsurancePreferenceUpdate, OnboardingRequest, UserResponse

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

    # Prevent duplicate onboarding
    try:
        existing = (
            await client.table("users").select("id").eq("id", user_id).execute()
        )
    except Exception as exc:
        logger.error(
            "DB lookup failed for user %s: %s", user_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding",
        )

    if existing.data:
        logger.warning("Duplicate onboarding attempt for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User profile already exists",
        )

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

    row = {
        "id": user_id,
        "email": email,
        "date_of_birth": payload.date_of_birth.isoformat(),
        "journey_stage": payload.journey_stage,
        "onboarding_completed": True,
    }

    try:
        response = await client.table("users").insert(row).execute()
    except Exception as exc:
        logger.error(
            "DB insert failed for user %s: %s", user_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding",
        )

    if not response.data:
        logger.error("Supabase returned no data after insert for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding",
        )

    created = response.data[0]
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
    client: SupabaseClient,
) -> InsurancePreference:
    """Fetch insurance_type and insurance_plan_name from the user's profile row.

    Returns null values rather than 404 when the profile exists but the
    columns are unset — the frontend treats null as "not yet saved".

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 500 for unexpected database failures.
    """
    try:
        response = (
            await client.table("users")
            .select("insurance_type, insurance_plan_name")
            .eq("id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB error fetching insurance preference for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insurance preference",
        )

    if not response.data:
        return InsurancePreference(insurance_type=None, insurance_plan_name=None)

    row = response.data[0]
    return InsurancePreference(
        insurance_type=row.get("insurance_type"),
        insurance_plan_name=row.get("insurance_plan_name"),
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
    client: SupabaseClient,
) -> InsurancePreference:
    """Write insurance_type and insurance_plan_name to the user's profile row.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if no user profile exists for the authenticated user.
        HTTPException: 422 if insurance_type is not a valid enum value.
        HTTPException: 500 for unexpected database failures.
    """
    try:
        response = (
            await client.table("users")
            .update(
                {
                    "insurance_type": payload.insurance_type.value,
                    "insurance_plan_name": payload.insurance_plan_name,
                }
            )
            .eq("id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "DB error updating insurance preference for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update insurance preference",
        )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    row = response.data[0]
    logger.info(
        "Insurance preference updated: user=%s type=%s", user_id, payload.insurance_type
    )
    return InsurancePreference(
        insurance_type=row.get("insurance_type"),
        insurance_plan_name=row.get("insurance_plan_name"),
    )
