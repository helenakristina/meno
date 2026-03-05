"""POST /api/appointment-prep/context — Appointment Prep Flow Step 1 endpoint.

Step 1 captures the user's context before generating the appointment prep narrative.
Three framing questions shape the tone and content of all generated outputs.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser, get_appointment_repo
from app.core.supabase import get_client
from app.repositories.appointment_repository import AppointmentRepository
from app.models.appointment import (
    AppointmentContext,
    CreateAppointmentContextRequest,
    CreateAppointmentContextResponse,
)
from supabase import AsyncClient

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
    )

    # Save context and get appointment ID
    appointment_id = await appointment_repo.save_context(user_id, context)

    # Log context creation (user_id hashed for privacy)
    logger.info(
        "Appointment prep started: appointment_id=%s appointment_type=%s goal=%s",
        appointment_id,
        context.appointment_type.value,
        context.goal.value,
    )

    return CreateAppointmentContextResponse(
        appointment_id=appointment_id,
        next_step="narrative",
    )
