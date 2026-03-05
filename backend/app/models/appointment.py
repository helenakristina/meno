"""
Pydantic models for the Appointment Prep Flow feature.

This includes models for:
- Context selection (Step 1)
- Full appointment prep data
- Generated outputs (provider summary, personal cheat sheet)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AppointmentType(str, Enum):
    """Type of appointment being prepared for."""

    new_provider = "new_provider"
    established_relationship = "established_relationship"


class AppointmentGoal(str, Enum):
    """Primary goal for the appointment."""

    understand_where_i_am = "understand_where_i_am"
    discuss_starting_hrt = "discuss_starting_hrt"
    evaluate_current_treatment = "evaluate_current_treatment"
    address_specific_symptom = "address_specific_symptom"


class DismissalExperience(str, Enum):
    """Prior dismissal experience with providers."""

    no = "no"
    once_or_twice = "once_or_twice"
    multiple_times = "multiple_times"


class AppointmentContext(BaseModel):
    """
    User's selections from Step 1 of Appointment Prep flow.

    These selections shape the tone and content of all generated outputs.
    """

    appointment_type: AppointmentType = Field(
        description="Type of appointment: new provider or established relationship"
    )
    goal: AppointmentGoal = Field(
        description="Primary goal for the appointment"
    )
    dismissed_before: DismissalExperience = Field(
        description="Whether the user has been dismissed by providers before"
    )


class ProviderSummary(BaseModel):
    """
    One-page clinical overview designed to be shared with or given to provider.

    Generated in Step 5, this is the professional-facing document.
    """

    content: str = Field(
        description="Markdown or HTML content suitable for sharing with provider"
    )
    generated_at: datetime = Field(
        description="Timestamp when this summary was generated"
    )


class PersonalCheatSheet(BaseModel):
    """
    Prioritized concerns and conversation anchors for the user.

    Generated in Step 5, this is the user's private reference document.
    May contain more candid language than the provider summary.
    """

    content: str = Field(
        description="Markdown content with prioritized concerns and key questions"
    )
    generated_at: datetime = Field(
        description="Timestamp when this cheat sheet was generated"
    )


class AppointmentPrepOutput(BaseModel):
    """
    Combined outputs from Step 5 of Appointment Prep flow.

    Contains both the provider summary and personal cheat sheet.
    """

    provider_summary: ProviderSummary
    personal_cheat_sheet: PersonalCheatSheet
    generated_at: datetime = Field(
        description="Timestamp when these outputs were generated"
    )


class AppointmentPrep(BaseModel):
    """
    Full appointment prep data across all steps.

    This is the complete state of a user's appointment preparation.
    """

    id: str = Field(description="UUID primary key")
    user_id: str = Field(description="User who created this appointment prep")
    context: AppointmentContext = Field(description="Initial context selections")
    narrative: str | None = Field(
        default=None,
        description="LLM-generated narrative summary of symptoms (Step 2), editable by user",
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Prioritized list of concerns from Step 3",
    )
    outputs: AppointmentPrepOutput | None = Field(
        default=None,
        description="Generated provider summary and personal cheat sheet from Step 5",
    )
    created_at: datetime = Field(description="When this prep was created")
    updated_at: datetime = Field(description="When this prep was last updated")

    model_config = {"from_attributes": True}


class AppointmentContextResponse(BaseModel):
    """
    Response model for the context step (Step 1).

    Sent to frontend to confirm selections were saved.
    """

    id: str = Field(description="Context ID")
    user_id: str = Field(description="User ID")
    appointment_type: AppointmentType
    goal: AppointmentGoal
    dismissed_before: DismissalExperience
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentPrepOutputResponse(BaseModel):
    """
    Response model for the complete appointment prep (all steps).

    Sent to frontend after outputs are generated.
    """

    id: str = Field(description="Prep ID")
    user_id: str = Field(description="User ID")
    context: AppointmentContextResponse
    narrative: str | None
    concerns: list[str]
    outputs: AppointmentPrepOutput | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Request/Response Models for API Endpoints
# ============================================================================


class CreateAppointmentContextRequest(BaseModel):
    """
    Request model for POST /api/appointment-prep/context (Step 1).

    User submits their answers to the three framing questions that shape
    the tone and content of all subsequent generated outputs.
    """

    appointment_type: AppointmentType = Field(
        description="Type of appointment: new provider or established relationship"
    )
    goal: AppointmentGoal = Field(
        description="Primary goal for the appointment"
    )
    dismissed_before: DismissalExperience = Field(
        description="Whether the user has been dismissed by providers before"
    )


class CreateAppointmentContextResponse(BaseModel):
    """
    Response model for POST /api/appointment-prep/context (Step 1).

    Returns the created appointment context ID and indicates the next step in the flow.
    """

    appointment_id: str = Field(description="UUID of the created appointment context")
    next_step: str = Field(
        default="narrative",
        description="Next step in the flow (always 'narrative' after Step 1)",
    )
