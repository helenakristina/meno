"""Appointment Prep Flow endpoints for Steps 1 and 2.

Step 1: Captures user context (appointment type, goal, dismissal experience).
Step 2: Generates LLM narrative from symptom logs and user context.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    CurrentUser,
    get_appointment_repo,
    get_user_repo,
    get_symptoms_repo,
    get_llm_service,
)
from app.core.supabase import get_client
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.llm import LLMService
from app.services.stats import calculate_frequency_stats, calculate_cooccurrence_stats
from app.models.appointment import (
    AppointmentContext,
    CreateAppointmentContextRequest,
    CreateAppointmentContextResponse,
    GenerateNarrativeRequest,
    AppointmentPrepNarrativeResponse,
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
    client: SupabaseClient,
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo),
    llm_service: LLMService = Depends(get_llm_service),
) -> AppointmentPrepNarrativeResponse:
    """Generate an LLM-powered narrative summary of symptom logs.

    Step 2 of the Appointment Prep Flow. Retrieves the user's symptom logs over the
    specified time period (default 60 days), calculates frequency and co-occurrence
    patterns, and uses an LLM to generate a clinical narrative suitable for sharing
    with or discussing with a healthcare provider.

    The narrative:
    - Uses "logs show" language (never diagnoses)
    - Highlights most frequent symptoms and notable patterns
    - Is grounded in the user's actual tracked data
    - Is tailored to the appointment context (type, goal, dismissal experience)

    Args:
        appointment_id: UUID of the appointment context created in Step 1.
        payload: GenerateNarrativeRequest with optional days_back parameter.
        user_id: Authenticated user ID (from Bearer token).
        appointment_repo: AppointmentRepository for data access.
        user_repo: UserRepository for user context.
        symptoms_repo: SymptomsRepository for symptom data.
        llm_service: LLMService for narrative generation.
        client: Supabase AsyncClient for reference data lookups.

    Returns:
        AppointmentPrepNarrativeResponse with appointment_id, narrative, and next_step.

    Raises:
        HTTPException: 400 if days_back is invalid (not 1-365).
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment context doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation fails or database operation fails.
    """
    # Verify appointment ownership and fetch context
    try:
        context = await appointment_repo.get_context(appointment_id, user_id)
    except HTTPException:
        raise

    logger.info(
        "Narrative generation started: appointment_id=%s days_back=%d",
        appointment_id,
        payload.days_back,
    )

    # Fetch user context (journey stage, age)
    try:
        journey_stage, age = await user_repo.get_context(user_id)
    except Exception as exc:
        logger.error(
            "Failed to fetch user context for narrative generation: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate narrative",
        )

    # Fetch symptom logs for the specified date range
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=payload.days_back)

    try:
        logs, _ = await symptoms_repo.get_logs(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,  # Fetch all logs for the period
        )
    except Exception as exc:
        logger.error(
            "Failed to fetch symptom logs for narrative: user=%s start=%s end=%s error=%s",
            user_id,
            start_date,
            end_date,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate narrative",
        )

    # If no logs, return a graceful message
    if not logs:
        empty_narrative = (
            f"No symptom logs found for the past {payload.days_back} days. "
            "Start logging symptoms to generate a narrative summary."
        )
        logger.info(
            "No symptom logs found: appointment_id=%s days_back=%d",
            appointment_id,
            payload.days_back,
        )
        await appointment_repo.save_narrative(appointment_id, user_id, empty_narrative)
        return AppointmentPrepNarrativeResponse(
            appointment_id=appointment_id,
            narrative=empty_narrative,
            next_step="prioritize",
        )

    # Convert SymptomLogResponse objects to dicts with raw symptom IDs for stats calculation
    raw_logs = [
        {"symptoms": [sym.id for sym in log.symptoms]} for log in logs
    ]

    # Fetch symptoms reference for stat calculations
    try:
        # Get all symptoms from the logs and fetch their reference data
        symptom_ids = set(sid for log in raw_logs for sid in log["symptoms"])
        if symptom_ids:
            response = (
                await client.table("symptoms_reference")
                .select("id, name, category")
                .in_("id", list(symptom_ids))
                .execute()
            )
            response_data = response.data if response.data and isinstance(response.data, list) else []
            symptoms_ref = {
                row["id"]: {"name": row["name"], "category": row["category"]}
                for row in response_data
            }
        else:
            symptoms_ref = {}
    except Exception as exc:
        logger.error(
            "Failed to fetch symptoms reference: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate narrative",
        )

    # Calculate symptom statistics
    try:
        frequency_stats = calculate_frequency_stats(raw_logs, symptoms_ref)
        cooccurrence_stats = calculate_cooccurrence_stats(raw_logs, symptoms_ref)
    except Exception as exc:
        logger.error(
            "Failed to calculate symptom stats: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate narrative",
        )

    logger.info(
        "Symptom stats calculated: appointment_id=%s freq_count=%d coocc_count=%d",
        appointment_id,
        len(frequency_stats),
        len(cooccurrence_stats),
    )

    # Build appointment-specific system and user prompts
    goal_str = context.goal.value.replace("_", " ").title()
    appt_type_str = context.appointment_type.value.replace("_", " ").title()
    age_str = str(age) if age else "not specified"

    system_prompt = (
        "You are preparing a clinical summary of symptom tracking data for a healthcare provider "
        "appointment. Your role is to present objective patterns from personal health tracking — "
        "not to diagnose, interpret causes, or recommend treatments.\n\n"
        "Rules:\n"
        "- Always use 'logs show' or 'data indicates' — never 'you have' or diagnose\n"
        "- Never suggest a medical condition, cause, or specific treatment\n"
        "- Frame observations as patterns worth discussing with a provider\n"
        "- Professional, neutral, clinical tone\n"
        "- Write 2–3 clear paragraphs suitable for a healthcare conversation\n"
        "- End by noting these patterns are worth discussing with a provider"
    )

    freq_lines = [
        f"- {s.symptom_name} ({s.category}): logged {s.count} time(s)"
        for s in frequency_stats[:10]
    ]
    freq_text = "\n".join(freq_lines) if freq_lines else "No symptom data."

    coocc_lines = [
        f"- {p.symptom1_name} + {p.symptom2_name}: "
        f"co-occurred {p.cooccurrence_count} time(s) "
        f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
        for p in cooccurrence_stats[:5]
    ]
    coocc_text = (
        "\n".join(coocc_lines) if coocc_lines else "No notable co-occurrence patterns."
    )

    user_prompt = (
        f"Write a 2–3 paragraph clinical summary for a healthcare appointment. "
        f"Patient context: {appt_type_str} appointment, goal is '{goal_str}', "
        f"age {age_str}, journey stage: {journey_stage}. "
        f"Symptom tracking covers {payload.days_back} days "
        f"({start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}).\n\n"
        f"Most frequently logged symptoms:\n{freq_text}\n\n"
        f"Symptom patterns (co-occurrences):\n{coocc_text}\n\n"
        "Write a clear, objective summary using 'logs show' language throughout. "
        "No diagnoses. No treatment recommendations."
    )

    # Call LLM to generate narrative
    logger.info(
        "Calling LLM to generate narrative: appointment_id=%s",
        appointment_id,
    )
    try:
        narrative = await llm_service.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=600,
            temperature=0.3,
        )
    except TimeoutError:
        logger.error(
            "LLM request timed out for appointment narrative: appointment_id=%s",
            appointment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary. Please try again.",
        )
    except Exception as exc:
        logger.error(
            "LLM generation failed for appointment narrative: appointment_id=%s error=%s",
            appointment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary. Please try again.",
        )

    logger.info(
        "Narrative generated: appointment_id=%s narrative_length=%d",
        appointment_id,
        len(narrative),
    )

    # Save narrative to database
    try:
        await appointment_repo.save_narrative(appointment_id, user_id, narrative)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to save narrative to database: appointment_id=%s error=%s",
            appointment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save narrative",
        )

    logger.info(
        "Narrative step completed: appointment_id=%s",
        appointment_id,
    )

    return AppointmentPrepNarrativeResponse(
        appointment_id=appointment_id,
        narrative=narrative,
        next_step="prioritize",
    )
