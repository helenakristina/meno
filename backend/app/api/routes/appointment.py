"""Appointment Prep Flow endpoints for Steps 1 and 2.

Step 1: Captures user context (appointment type, goal, dismissal experience).
Step 2: Generates LLM narrative from symptom logs and user context.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from io import BytesIO

from app.api.dependencies import (
    CurrentUser,
    get_appointment_repo,
    get_user_repo,
    get_symptoms_repo,
    get_llm_service,
    get_storage_service,
)
from app.core.supabase import get_client
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.llm import LLMService
from app.services.storage import StorageService
from app.services.stats import calculate_frequency_stats, calculate_cooccurrence_stats
from app.models.appointment import (
    AppointmentContext,
    CreateAppointmentContextRequest,
    CreateAppointmentContextResponse,
    GenerateNarrativeRequest,
    AppointmentPrepNarrativeResponse,
    PrioritizeConcernsRequest,
    AppointmentPrepPrioritizeResponse,
    ScenarioCard,
    AppointmentPrepScenariosResponse,
    AppointmentPrepGenerateResponse,
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
    raw_logs = [{"symptoms": [sym.id for sym in log.symptoms]} for log in logs]

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
            response_data = (
                response.data
                if response.data and isinstance(response.data, list)
                else []
            )
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
    except HTTPException:
        raise

    logger.info(
        "Prioritize concerns started: appointment_id=%s concerns_count=%d",
        appointment_id,
        len(payload.concerns),
    )

    # Save concerns
    try:
        await appointment_repo.save_concerns(appointment_id, user_id, payload.concerns)
    except HTTPException:
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
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    llm_service: LLMService = Depends(get_llm_service),
) -> AppointmentPrepScenariosResponse:
    """Generate practice scenarios for Step 4.

    Fetches appointment context, user concerns, and journey stage. Selects 5-7 relevant
    dismissal scenarios based on the user's appointment type, goal, and prior dismissal
    experience. Calls LLM to generate suggestions for each scenario.

    Args:
        appointment_id: UUID of the appointment context from Step 1.
        user_id: Authenticated user ID.
        appointment_repo: AppointmentRepository for context access.
        user_repo: UserRepository for user context.
        llm_service: LLMService for scenario generation.

    Returns:
        AppointmentPrepScenariosResponse with scenario cards and next step.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation or database operation fails.
    """
    # Verify appointment ownership and fetch context
    try:
        context = await appointment_repo.get_context(appointment_id, user_id)
    except HTTPException:
        raise

    logger.info(
        "Scenario generation started: appointment_id=%s goal=%s dismissed=%s",
        appointment_id,
        context.goal.value,
        context.dismissed_before.value,
    )

    # Fetch user context (journey stage, age)
    try:
        journey_stage, age = await user_repo.get_context(user_id)
    except Exception as exc:
        logger.error(
            "Failed to fetch user context for scenarios: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenarios",
        )

    # Select scenarios based on context
    # Always include general scenarios, then add goal-specific ones
    scenarios_to_generate = _select_scenarios(context, journey_stage)

    logger.info(
        "Selected %d scenarios for generation",
        len(scenarios_to_generate),
    )

    # Fetch concerns from Step 3 (default to empty if not saved yet)
    concerns: list[str] = []
    try:
        # Get full context row to check if concerns field exists
        context_response = (
            await appointment_repo.client.table("appointment_prep_contexts")
            .select("concerns")
            .eq("id", appointment_id)
            .eq("user_id", user_id)
            .execute()
        )
        if context_response.data and len(context_response.data) > 0:
            data = context_response.data[0]
            if isinstance(data, dict):
                concerns_data = data.get("concerns")
                if isinstance(concerns_data, list):
                    concerns = concerns_data
    except Exception as exc:
        logger.warning(
            "Failed to fetch concerns from Step 3: %s",
            exc,
        )
        concerns = []

    # Call LLM to generate suggestions
    try:
        raw_suggestions = await llm_service.generate_scenario_suggestions(
            scenarios_to_generate=scenarios_to_generate,
            concerns=concerns,
            appointment_type=context.appointment_type.value,
            goal=context.goal.value,
            dismissed_before=context.dismissed_before.value,
            user_age=age,
        )
    except TimeoutError:
        logger.error(
            "LLM request timed out for scenarios: appointment_id=%s",
            appointment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenarios. Please try again.",
        )
    except Exception as exc:
        logger.error(
            "LLM generation failed for scenarios: appointment_id=%s error=%s",
            appointment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenarios. Please try again.",
        )

    # Parse JSON response and build scenario cards
    try:
        suggestions_list = json.loads(raw_suggestions)
        if not isinstance(suggestions_list, list):
            suggestions_list = [suggestions_list]
    except json.JSONDecodeError:
        logger.error(
            "Failed to parse LLM response as JSON: response=%s",
            raw_suggestions[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenarios",
        )

    # Build scenario cards
    scenario_cards: list[ScenarioCard] = []
    for idx, (scenario_title, suggestion_data) in enumerate(
        zip(scenarios_to_generate, suggestions_list)
    ):
        suggestion_text = (
            suggestion_data.get("suggestion", "")
            if isinstance(suggestion_data, dict)
            else str(suggestion_data)
        )
        category = _get_scenario_category(scenario_title)

        scenario_cards.append(
            ScenarioCard(
                id=f"scenario-{idx + 1}",
                title=scenario_title,
                situation=f"If your provider says something like: '{scenario_title}'",
                suggestion=suggestion_text,
                category=category,
            )
        )

    # Save scenarios
    try:
        scenarios_to_save = [
            {
                "id": card.id,
                "title": card.title,
                "situation": card.situation,
                "suggestion": card.suggestion,
                "category": card.category,
            }
            for card in scenario_cards
        ]
        await appointment_repo.save_scenarios(
            appointment_id, user_id, scenarios_to_save
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to save scenarios: appointment_id=%s error=%s",
            appointment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save scenarios",
        )

    logger.info(
        "Scenarios generated and saved: appointment_id=%s count=%d",
        appointment_id,
        len(scenario_cards),
    )

    return AppointmentPrepScenariosResponse(
        appointment_id=appointment_id,
        scenarios=scenario_cards,
        next_step="generate",
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
    appointment_repo: AppointmentRepository = Depends(get_appointment_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    llm_service: LLMService = Depends(get_llm_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> AppointmentPrepGenerateResponse:
    """Generate and save PDF outputs for Step 5.

    Fetches all appointment prep data (narrative, concerns, scenarios), generates
    provider summary and personal cheat sheet content via LLM, converts to PDFs,
    uploads to Supabase Storage, and returns public URLs.

    Args:
        appointment_id: UUID of the appointment context from Step 1.
        user_id: Authenticated user ID.
        appointment_repo: AppointmentRepository for data access.
        user_repo: UserRepository for user context.
        llm_service: LLMService for content generation.
        storage_service: StorageService for PDF uploads.

    Returns:
        AppointmentPrepGenerateResponse with PDF URLs.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if appointment doesn't exist or doesn't belong to user.
        HTTPException: 500 if LLM generation, PDF conversion, or upload fails.
    """
    # Verify appointment ownership and fetch context
    try:
        context = await appointment_repo.get_context(appointment_id, user_id)
    except HTTPException:
        raise

    logger.info(
        "PDF generation started: appointment_id=%s",
        appointment_id,
    )

    # Fetch full appointment data
    try:
        context_response = (
            await appointment_repo.client.table("appointment_prep_contexts")
            .select("narrative, concerns")
            .eq("id", appointment_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not context_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment context not found",
            )

        context_row = context_response.data[0]
        narrative = context_row.get("narrative", "No narrative available.")
        concerns = context_row.get("concerns", [])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch appointment data: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outputs",
        )

    # Fetch user context
    try:
        _journey_stage, age = await user_repo.get_context(user_id)
    except Exception as exc:
        logger.error("Failed to fetch user context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outputs",
        )

    # Ensure narrative and concerns are proper types
    narrative_text: str = narrative if isinstance(narrative, str) else str(narrative)
    concerns_list: list = concerns if isinstance(concerns, list) else []

    # Generate provider summary
    try:
        provider_summary_md = await llm_service.generate_pdf_content(
            content_type="provider_summary",
            narrative=narrative_text,
            concerns=concerns_list,
            appointment_type=context.appointment_type.value,
            goal=context.goal.value,
            user_age=age,
        )
    except TimeoutError:
        logger.error(
            "LLM request timed out for provider summary: appointment_id=%s",
            appointment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate provider summary. Please try again.",
        )
    except Exception as exc:
        logger.error(
            "LLM generation failed for provider summary: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate provider summary",
        )

    # Generate personal cheat sheet
    try:
        cheatsheet_md = await llm_service.generate_pdf_content(
            content_type="personal_cheatsheet",
            narrative=narrative_text,
            concerns=concerns_list,
            appointment_type=context.appointment_type.value,
            goal=context.goal.value,
            user_age=age,
        )
    except TimeoutError:
        logger.error(
            "LLM request timed out for cheat sheet: appointment_id=%s",
            appointment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cheat sheet. Please try again.",
        )
    except Exception as exc:
        logger.error(
            "LLM generation failed for cheat sheet: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cheat sheet",
        )

    # Convert markdown to PDFs
    try:
        provider_summary_pdf = _markdown_to_pdf(
            provider_summary_md,
            title="Provider Summary",
        )
        cheatsheet_pdf = _markdown_to_pdf(
            cheatsheet_md,
            title="Personal Cheat Sheet",
        )
    except Exception as exc:
        logger.error(
            "Failed to convert markdown to PDF: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF",
        )

    # Upload PDFs to Supabase Storage
    try:
        summary_url = await storage_service.upload_pdf(
            bucket="appointment-prep",
            path=f"{user_id}/{appointment_id}/provider-summary.pdf",
            content=provider_summary_pdf,
        )
        cheatsheet_url = await storage_service.upload_pdf(
            bucket="appointment-prep",
            path=f"{user_id}/{appointment_id}/personal-cheatsheet.pdf",
            content=cheatsheet_pdf,
        )
    except Exception as exc:
        logger.error(
            "Failed to upload PDFs to storage: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload PDF files",
        )

    logger.info(
        "PDFs generated and uploaded: appointment_id=%s",
        appointment_id,
    )

    return AppointmentPrepGenerateResponse(
        appointment_id=appointment_id,
        provider_summary_url=summary_url,
        personal_cheat_sheet_url=cheatsheet_url,
        message="Your appointment prep is ready!",
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _select_scenarios(context: AppointmentContext, journey_stage: str) -> list[str]:
    """Select 5-7 scenarios based on appointment context.

    Uses real dismissals that women experience with healthcare providers,
    selected based on appointment goal and prior dismissal experience.

    Args:
        context: AppointmentContext with appointment_type, goal, dismissed_before.
        journey_stage: User's journey stage (exploration, preparation, transition, active).

    Returns:
        List of 5-7 scenario titles (real dismissals).
    """
    scenarios = []

    # Goal-specific scenarios (what providers commonly dismiss based on what you're asking for)
    if context.goal.value == "explore_hrt":
        scenarios.extend(
            [
                "Hormone therapy increases breast cancer risk",
                "I don't prescribe that, I give the birth control pill instead",
                "Let's try an antidepressant first",
            ]
        )
    elif context.goal.value == "optimize_current_treatment":
        scenarios.extend(
            [
                "Your symptoms aren't severe enough to treat",
                "That dose is already too high",
                "Let's try lifestyle changes first",
            ]
        )
    elif context.goal.value == "assess_status":
        scenarios.extend(
            [
                "Your symptoms will go away on their own",
                "You're just stressed or anxious",
            ]
        )

    # Dismissal experience-specific scenarios
    if context.dismissed_before.value == "multiple_times":
        scenarios.extend(
            [
                "You're too old to start hormone therapy",
                "What are the triggers?",
            ]
        )
    elif context.dismissed_before.value == "once_or_twice":
        scenarios.extend(
            [
                "What are the triggers?",
            ]
        )

    # Cap at 7 scenarios, ensuring diversity
    # Deduplicate and limit
    scenarios = list(dict.fromkeys(scenarios))[:7]

    return scenarios


def _get_scenario_category(title: str) -> str:
    """Determine scenario category from title.

    Args:
        title: Scenario title text.

    Returns:
        Category string for frontend grouping (hrt-concerns, dismissal-psychology,
        alternative-treatment, treatment-adjustment, deflection, dismissal, general).
    """
    title_lower = title.lower()

    if "breast cancer" in title_lower or "hormone therapy increases" in title_lower:
        return "hrt-concerns"
    elif "antidepressant" in title_lower or "stressed" in title_lower or "anxious" in title_lower:
        return "dismissal-psychology"
    elif "birth control" in title_lower or "pill" in title_lower:
        return "alternative-treatment"
    elif "dose" in title_lower or "high" in title_lower or "severe" in title_lower:
        return "treatment-adjustment"
    elif "triggers" in title_lower or "lifestyle" in title_lower:
        return "deflection"
    elif "too old" in title_lower or "go away" in title_lower:
        return "dismissal"
    else:
        return "general"


def _inline_md(text: str) -> str:
    """Convert inline markdown to reportlab XML tags.

    reportlab's Paragraph supports <b>, <i>, and <font> tags natively.
    Process bold-italic first to avoid partial matches.
    """
    # Bold italic: ***text*** or ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", r"<b><i>\1</i></b>", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"<b><i>\1</i></b>", text)
    # Bold: **text** or __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", r"<b>\1</b>", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"<b>\1</b>", text)
    # Italic: *text* or _text_
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    # Inline code: `text`
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    return text


def _markdown_to_pdf(markdown_text: str, title: str = "") -> bytes:
    """Convert markdown text to PDF bytes using reportlab.

    Handles: headings (h1–h4), bullet lists, numbered lists, paragraphs,
    and inline formatting (bold, italic, bold-italic, inline code).

    Args:
        markdown_text: Markdown-formatted text.
        title: Document title shown centered at the top.

    Returns:
        PDF content as bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=HexColor("#1f2937"),
        spaceAfter=12,
        alignment=1,
    )
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=HexColor("#1f2937"),
        spaceBefore=10,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=HexColor("#374151"),
        spaceBefore=8,
        spaceAfter=4,
    )
    h3_style = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontSize=11,
        textColor=HexColor("#374151"),
        spaceBefore=6,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        leftIndent=20,
        spaceAfter=2,
    )
    numbered_style = ParagraphStyle(
        "Numbered",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        leftIndent=20,
        spaceAfter=2,
    )

    story = []

    if title:
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2 * inch))

    for line in markdown_text.split("\n"):
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 0.06 * inch))
        elif stripped.startswith("#### "):
            story.append(Paragraph(_inline_md(stripped[5:]), h3_style))
        elif stripped.startswith("### "):
            story.append(Paragraph(_inline_md(stripped[4:]), h3_style))
        elif stripped.startswith("## "):
            story.append(Paragraph(_inline_md(stripped[3:]), h2_style))
        elif stripped.startswith("# "):
            story.append(Paragraph(_inline_md(stripped[2:]), h1_style))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph(f"• {_inline_md(stripped[2:])}", bullet_style))
        elif re.match(r"^\d+\. ", stripped):
            m = re.match(r"^(\d+)\. (.+)", stripped)
            if m:
                story.append(
                    Paragraph(f"{m.group(1)}. {_inline_md(m.group(2))}", numbered_style)
                )
        elif stripped in ("---", "***", "___"):
            story.append(Spacer(1, 0.08 * inch))
        else:
            story.append(Paragraph(_inline_md(stripped), body_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
