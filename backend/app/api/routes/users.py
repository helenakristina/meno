import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from app.api.dependencies import CurrentUser
from app.core.supabase import get_client
from app.models.users import OnboardingRequest, UserResponse

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
