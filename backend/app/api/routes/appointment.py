"""Appointment Prep Flow endpoints (Steps 1–5).

Thin HTTP wrappers over AppointmentService — each handler validates input,
calls the service, and converts domain exceptions to HTTP responses.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from app.api.dependencies import (
    CurrentUser,
    get_appointment_repo,
    get_storage_service,
    get_appointment_service,
)
from app.core.supabase import get_client
from app.exceptions import DatabaseError, EntityNotFoundError
from app.repositories.appointment_repository import AppointmentRepository
from app.services.appointment import AppointmentService
from app.services.storage import StorageService
from app.models.appointment import (
    AppointmentContext,
    CreateAppointmentContextRequest,
    CreateAppointmentContextResponse,
    GenerateNarrativeRequest,
    AppointmentPrepNarrativeResponse,
    PrioritizeConcernsRequest,
    AppointmentPrepPrioritizeResponse,
    AppointmentPrepScenariosResponse,
    AppointmentPrepGenerateResponse,
    AppointmentPrepHistoryListResponse,
    AppointmentPrepHistoryResponse,
)
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/appointment-prep", tags=["appointment"])

SupabaseClient = Annotated[AsyncClient, Depends(get_client)]


@router.post(
    "/context",
    response_model=CreateAppointmentContextResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start appointment prep with context",
    description=(
        "Step 1 of Appointment Prep Flow. User submits answers to three framing questions "
        "that shape the tone and content of all generated outputs. Returns appointment ID "
        "and next step."
    ),
)
async def create_appointment_context(
    payload: CreateAppointmentContextRequest,
    user_id: CurrentUser,
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
) -> CreateAppointmentContextResponse:
    """Create appointment prep context (Step 1 of Appointment Prep Flow).

    Captures the user's answers to three framing questions:
    1. What kind of appointment is this? (new provider vs established relationship)
    2. What is the primary goal? (understand where I am, discuss HRT, etc.)
    3. Have you been dismissed by providers before? (no, once/twice, multiple times)

    These answers shape the tone and content of all subsequent generated outputs,
    including the LLM-generated narrative, prioritized concerns, and scenario cards.

    Args:
        payload: CreateAppointmentContextRequest with appointment_type, goal, dismissed_before.
        user_id: Authenticated user ID (from Bearer token).
        appointment_repo: AppointmentRepository for data access.

    Returns:
        CreateAppointmentContextResponse with appointment_id and next_step.

    Raises:
        HTTPException: 400 if invalid input (Pydantic validation).
        HTTPException: 401 if not authenticated.
        HTTPException: 500 if database operation fails.
    """
    # Create AppointmentContext from request
    context = AppointmentContext(
        appointment_type=payload.appointment_type,
        goal=payload.goal,
        dismissed_before=payload.dismissed_before,
        urgent_symptom=payload.urgent_symptom,
    )

    # Save context and get appointment ID
    appointment_id = await appointment_repo.save_context(user_id, context)

    # Log context creation (user_id hashed for privacy)
    logger.info(
        "Appointment prep started: appointment_id=%s appointment_type=%s goal=%s has_urgent=%s",
        appointment_id,
        context.appointment_type.value,
        context.goal.value,
        bool(context.urgent_symptom),
    )

    return CreateAppointmentContextResponse(
        appointment_id=appointment_id,
        next_step="narrative",
    )


@router.post(
    "/{appointment_id}/narrative",
    response_model=AppointmentPrepNarrativeResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate narrative from symptom logs",
    description=(
        "Step 2 of Appointment Prep Flow. Fetches user's symptom logs, calculates patterns, "
        "and uses LLM to generate a clinical narrative summary. Returns the narrative and "
        "next step in the flow."
    ),
)
async def generate_appointment_narrative(
    appointment_id: str,
    payload: GenerateNarrativeRequest,
    user_id: CurrentUser,
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentPrepNarrativeResponse:
    """Generate an LLM-powered narrative summary of symptom logs (Step 2).

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment context doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation or database operation fails.
    """
    try:
        return await appointment_service.generate_narrative(
            appointment_id=appointment_id,
            user_id=user_id,
            days_back=payload.days_back,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DatabaseError as exc:
        logger.error("Narrative generation failed: appointment_id=%s error=%s", appointment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate narrative. Please try again.",
        )


@router.put(
    "/{appointment_id}/prioritize",
    response_model=AppointmentPrepPrioritizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Save prioritized concerns",
    description=(
        "Step 3 of Appointment Prep Flow. User submits their prioritized concerns in ranked order. "
        "Returns confirmation and next step."
    ),
)
async def prioritize_concerns(
    appointment_id: str,
    payload: PrioritizeConcernsRequest,
    user_id: CurrentUser,
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
) -> AppointmentPrepPrioritizeResponse:
    """Save prioritized concerns from Step 3.

    Stores the user's ranked list of concerns to the appointment context.
    These concerns shape the scenario generation in Step 4 and the outputs in Step 5.

    Args:
        appointment_id: UUID of the appointment context from Step 1.
        payload: PrioritizeConcernsRequest with ordered concerns list.
        user_id: Authenticated user ID.
        appointment_repo: AppointmentRepository for data access.

    Returns:
        AppointmentPrepPrioritizeResponse confirming save and next step.

    Raises:
        HTTPException: 400 if concerns list is empty.
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment doesn't exist or doesn't belong to user.
        HTTPException: 500 if database operation fails.
    """
    # Verify appointment ownership
    try:
        await appointment_repo.get_context(appointment_id, user_id)
    except (EntityNotFoundError, DatabaseError):
        raise

    logger.info(
        "Prioritize concerns started: appointment_id=%s concerns_count=%d",
        appointment_id,
        len(payload.concerns),
    )

    # Save concerns
    try:
        await appointment_repo.save_concerns(appointment_id, user_id, payload.concerns)
    except (EntityNotFoundError, DatabaseError):
        raise
    except Exception as exc:
        logger.error(
            "Failed to save concerns: appointment_id=%s error=%s",
            appointment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save concerns",
        )

    logger.info(
        "Concerns saved: appointment_id=%s",
        appointment_id,
    )

    return AppointmentPrepPrioritizeResponse(
        appointment_id=appointment_id,
        concerns=payload.concerns,
        next_step="scenarios",
    )


@router.post(
    "/{appointment_id}/scenarios",
    response_model=AppointmentPrepScenariosResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate practice scenarios",
    description=(
        "Step 4 of Appointment Prep Flow. Generates 5-7 dismissal scenarios and LLM-suggested responses. "
        "Scenarios are selected based on appointment context and user's prior dismissal experience."
    ),
)
async def generate_appointment_scenarios(
    appointment_id: str,
    user_id: CurrentUser,
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentPrepScenariosResponse:
    """Generate practice scenarios for Step 4.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation or database operation fails.
    """
    try:
        return await appointment_service.generate_scenarios(
            appointment_id=appointment_id,
            user_id=user_id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DatabaseError as exc:
        logger.error("Scenario generation failed: appointment_id=%s error=%s", appointment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenarios. Please try again.",
        )


@router.post(
    "/{appointment_id}/generate",
    response_model=AppointmentPrepGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate PDF outputs",
    description=(
        "Step 5 of Appointment Prep Flow. Generates provider summary and personal cheat sheet PDFs, "
        "uploads them to Supabase Storage, and returns shareable URLs."
    ),
)
async def generate_appointment_outputs(
    appointment_id: str,
    user_id: CurrentUser,
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentPrepGenerateResponse:
    """Generate and upload PDF outputs (Step 5).

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation, PDF conversion, or upload fails.
    """
    try:
        return await appointment_service.generate_pdf(
            appointment_id=appointment_id,
            user_id=user_id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DatabaseError as exc:
        logger.error("PDF generation failed: appointment_id=%s error=%s", appointment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outputs. Please try again.",
        )


@router.get(
    "/history",
    response_model=AppointmentPrepHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get appointment prep history",
    description=(
        "Retrieve list of all appointment preps the user has generated. "
        "Returns metadata with dates and paths to download PDFs."
    ),
)
async def get_appointment_prep_history(
    user_id: CurrentUser,
    limit: int = 50,
    offset: int = 0,
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    storage_service: StorageService = Depends(get_storage_service),
) -> AppointmentPrepHistoryListResponse:
    """Get user's appointment prep history with download links.

    Returns list of all appointment preps generated, newest first.
    Includes paths to download PDFs via signed URLs.

    Args:
        user_id: Authenticated user ID.
        limit: Max results to return (default 50, max 100).
        offset: Pagination offset (default 0).
        appointment_repo: AppointmentRepository for data access.
        storage_service: StorageService for generating download URLs.

    Returns:
        AppointmentPrepHistoryListResponse with list of preps and total count.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 500 if database operation fails.
    """
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    logger.info(
        "Fetching appointment prep history: user=%s limit=%d offset=%d",
        hash_user_id(user_id),
        limit,
        offset,
    )

    try:
        preps, total = await appointment_repo.get_user_prep_history(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
    except (EntityNotFoundError, DatabaseError):
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch history: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch appointment prep history",
        )

    # Build response with download URLs
    history_items: list[AppointmentPrepHistoryResponse] = []
    for prep in preps:
        try:
            # Generate signed URLs for both PDFs (24-hour expiration)
            summary_url = await storage_service.create_signed_url(
                bucket="appointment-prep",
                path=prep.get("provider_summary_path"),
                expires_in=86400,  # 24 hours
            )
            cheatsheet_url = await storage_service.create_signed_url(
                bucket="appointment-prep",
                path=prep.get("personal_cheatsheet_path"),
                expires_in=86400,  # 24 hours
            )

            history_items.append(
                AppointmentPrepHistoryResponse(
                    id=prep.get("id"),
                    appointment_id=prep.get("appointment_id"),
                    generated_at=prep.get("generated_at"),
                    provider_summary_path=summary_url,
                    personal_cheatsheet_path=cheatsheet_url,
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to generate signed URL for prep %s: %s",
                prep.get("id"),
                exc,
            )
            # Continue processing other preps
            continue

    logger.info(
        "Returning %d appointment preps from history (total %d)",
        len(history_items),
        total,
    )

    return AppointmentPrepHistoryListResponse(
        preps=history_items,
        total=total,
    )


