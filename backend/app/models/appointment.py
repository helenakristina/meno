"""
Pydantic models for the Appointment Prep Flow feature.

This includes models for:
- Context selection (Step 1)
- Full appointment prep data
- Generated outputs (provider summary, personal cheat sheet)
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppointmentType(str, Enum):
    """Type of appointment being prepared for."""

    new_provider = "new_provider"
    established_relationship = "established_relationship"


class AppointmentGoal(str, Enum):
    """Primary goal for the appointment."""

    assess_status = "assess_status"
    explore_hrt = "explore_hrt"
    optimize_current_treatment = "optimize_current_treatment"
    urgent_symptom = "urgent_symptom"


class DismissalExperience(str, Enum):
    """Prior dismissal experience with providers."""

    no = "no"
    once_or_twice = "once_or_twice"
    multiple_times = "multiple_times"


class Concern(BaseModel):
    """A single prioritized concern with optional contextual comment.

    The comment lets users add detail that shapes how the concern is
    represented in provider-facing and patient-facing documents.
    """

    text: str = Field(description="The concern text", min_length=1, max_length=500)
    comment: str | None = Field(
        default=None,
        description="Optional context the user wants their provider to know about this concern",
        max_length=200,
    )


class AppointmentContext(BaseModel):
    """
    User's selections from Step 1 of Appointment Prep flow.

    These selections shape the tone and content of all generated outputs.
    """

    appointment_type: AppointmentType = Field(
        description="Type of appointment: new provider or established relationship"
    )
    goal: AppointmentGoal = Field(description="Primary goal for the appointment")
    dismissed_before: DismissalExperience = Field(
        description="Whether the user has been dismissed by providers before"
    )
    urgent_symptom: str | None = Field(
        default=None,
        description="Which symptom is urgent (only set when goal is 'urgent_symptom')",
    )
    what_have_you_tried: str | None = Field(
        default=None,
        description="What treatments or approaches the user has already tried (Step 3.5)",
    )
    specific_ask: str | None = Field(
        default=None,
        description="What the user specifically wants from this appointment (Step 3.5)",
    )
    history_clotting_risk: Literal["yes", "no", "not_sure"] | None = Field(
        default=None,
        description="Personal or family history of blood clots or clotting disorders (Step 3.5)",
    )
    history_breast_cancer: Literal["yes", "no", "not_sure"] | None = Field(
        default=None,
        description="Personal or family history of breast cancer (Step 3.5)",
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
    concerns: list[Concern] = Field(
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
    urgent_symptom: str | None = Field(
        default=None,
        description="Which symptom is urgent (only set when goal is 'urgent_symptom')",
    )
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
    concerns: list[Concern]
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
    goal: AppointmentGoal = Field(description="Primary goal for the appointment")
    dismissed_before: DismissalExperience = Field(
        description="Whether the user has been dismissed by providers before"
    )
    urgent_symptom: str | None = Field(
        default=None,
        max_length=500,
        description="Which symptom is urgent (max 500 chars; only set when goal is 'urgent_symptom')",
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


class GenerateNarrativeRequest(BaseModel):
    """
    Request model for POST /api/appointment-prep/{id}/narrative (Step 2).

    User submits optional parameters for narrative generation, defaulting to 60 days
    of symptom history.
    """

    days_back: int = Field(
        default=60,
        ge=1,
        le=365,
        description="How many days of symptom logs to include (1-365 days)",
    )


class AppointmentPrepNarrativeResponse(BaseModel):
    """
    Response model for POST /api/appointment-prep/{id}/narrative (Step 2).

    Returns the generated narrative summary and next step in the flow.
    """

    appointment_id: str = Field(description="UUID of the appointment context")
    narrative: str = Field(description="LLM-generated narrative summary (markdown)")
    next_step: str = Field(
        default="prioritize",
        description="Next step in the flow (always 'prioritize' after Step 2)",
    )


class SaveNarrativeRequest(BaseModel):
    """Request model for PUT /api/appointment-prep/{id}/narrative.

    Allows the user to save their edited narrative from Step 2.
    """

    narrative: str = Field(
        description="User-edited narrative text (markdown)",
        min_length=1,
        max_length=10000,
    )


# ============================================================================
# Step 3: Prioritize Concerns
# ============================================================================


class PrioritizeConcernsRequest(BaseModel):
    """
    Request model for PUT /api/appointment-prep/{id}/prioritize (Step 3).

    User submits their prioritized concerns in ranked order.
    Each concern has a required text and optional comment for context.
    """

    concerns: list[Concern] = Field(
        min_length=1,
        description="Ordered list of prioritized concerns (non-empty)",
    )


class AppointmentPrepPrioritizeResponse(BaseModel):
    """
    Response model for PUT /api/appointment-prep/{id}/prioritize (Step 3).

    Confirms concerns were saved and indicates next step.
    """

    appointment_id: str = Field(description="UUID of the appointment context")
    concerns: list[Concern] = Field(description="Saved prioritized concerns")
    next_step: str = Field(
        default="scenarios",
        description="Next step in the flow (always 'scenarios' after Step 3)",
    )


class SaveQualitativeContextRequest(BaseModel):
    """
    Request model for PUT /api/appointment-prep/{id}/qualitative-context (Step 3.5).

    User submits additional qualitative context that shapes the tone and content
    of generated documents. All fields are optional — partial saves are valid.
    """

    what_have_you_tried: str | None = Field(
        default=None,
        max_length=500,
        description="Treatments or approaches already tried (max 500 chars)",
    )
    specific_ask: str | None = Field(
        default=None,
        max_length=300,
        description="What the user specifically wants from this appointment (max 300 chars)",
    )
    history_clotting_risk: Literal["yes", "no", "not_sure"] | None = Field(
        default=None,
        description="Personal or family history of blood clots or clotting disorders",
    )
    history_breast_cancer: Literal["yes", "no", "not_sure"] | None = Field(
        default=None,
        description="Personal or family history of breast cancer",
    )


class SaveQualitativeContextResponse(BaseModel):
    """
    Response model for PUT /api/appointment-prep/{id}/qualitative-context (Step 3.5).
    """

    appointment_id: str = Field(description="UUID of the appointment context")
    next_step: str = Field(
        default="scenarios",
        description="Next step in the flow (always 'scenarios' after Step 3.5)",
    )


# ============================================================================
# Step 4: Generate Scenarios
# ============================================================================


class ScenarioSource(BaseModel):
    """A single RAG source document grounding a scenario suggestion."""

    title: str
    excerpt: str


class ScenarioCard(BaseModel):
    """
    A single scenario card for practice responses.

    Represents one dismissal situation and a suggested response.
    """

    id: str = Field(description="Unique scenario ID (e.g. 'scenario-1')")
    title: str = Field(
        description="The dismissal scenario (e.g. 'Brain fog is just normal aging')"
    )
    situation: str = Field(
        description="The dismissal scenario text (e.g. 'If your provider says...')"
    )
    suggestion: str = Field(
        description="LLM-generated response suggestion with evidence-based language and source links"
    )
    category: str = Field(description="Scenario category based on dismissal type")
    sources: list[ScenarioSource] = Field(
        default_factory=list,
        description="RAG source documents used to ground this scenario (each has 'title' and 'excerpt')",
    )


class AppointmentPrepScenariosResponse(BaseModel):
    """
    Response model for POST /api/appointment-prep/{id}/scenarios (Step 4).

    Returns generated scenario cards and next step.
    """

    appointment_id: str = Field(description="UUID of the appointment context")
    scenarios: list[ScenarioCard] = Field(
        description="List of generated scenario cards"
    )
    next_step: str = Field(
        default="generate",
        description="Next step in the flow (always 'generate' after Step 4)",
    )


# ============================================================================
# Step 5: Generate Outputs
# ============================================================================


class AppointmentPrepGenerateResponse(BaseModel):
    """
    Response model for POST /api/appointment-prep/{id}/generate (Step 5).

    Returns URLs to the generated PDF outputs.
    """

    appointment_id: str = Field(description="UUID of the appointment context")
    provider_summary_url: str = Field(description="Public URL to provider summary PDF")
    personal_cheat_sheet_url: str = Field(
        description="Public URL to personal cheat sheet PDF"
    )
    message: str = Field(
        default="Your appointment prep is ready!",
        description="Confirmation message",
    )


# ============================================================================
# Appointment Prep History
# ============================================================================


class AppointmentPrepHistoryResponse(BaseModel):
    """
    Single item in appointment prep history.

    Contains metadata about a generated appointment prep with download links.
    """

    id: str = Field(description="Metadata record ID")
    appointment_id: str = Field(description="Associated appointment prep ID")
    generated_at: str = Field(
        description="ISO format datetime when PDFs were generated"
    )
    provider_summary_path: str = Field(description="Signed URL to provider summary PDF")
    personal_cheatsheet_path: str = Field(
        description="Signed URL to personal cheat sheet PDF"
    )


# ---------------------------------------------------------------------------
# Phase 4: Structured LLM response models for PDF generation
# ---------------------------------------------------------------------------


class ProviderSummaryResponse(BaseModel):
    """LLM JSON response for the provider-facing appointment summary PDF.

    extra="ignore" lets unexpected LLM fields pass silently.
    Missing required fields raise ValidationError — the caller converts this
    to DatabaseError so the user can retry (hard-fail, no degraded PDF).

    Note: symptom_picture removed in Phase 5 — the user's narrative is inserted
    verbatim by the PDF builder instead of being rewritten by the LLM.
    Note: closing removed — the opening field already frames the encounter context;
    a separate closing section was redundant on a one-page provider document.
    """

    model_config = ConfigDict(extra="ignore")

    opening: str
    key_patterns: str = ""


class QuestionGroup(BaseModel):
    """A topic-grouped set of provider questions for the cheatsheet."""

    model_config = ConfigDict(extra="ignore")

    topic: str
    questions: list[str]


class CheatsheetResponse(BaseModel):
    """LLM JSON response for the patient-facing cheatsheet PDF.

    extra="ignore" for the same reason as ProviderSummaryResponse.
    """

    model_config = ConfigDict(extra="ignore")

    opening_statement: str
    question_groups: list[QuestionGroup] = []


class AppointmentPrepHistoryListResponse(BaseModel):
    """
    List of all appointment preps user has generated.

    Provides paginated history with total count for UI pagination.
    """

    preps: list[AppointmentPrepHistoryResponse] = Field(
        description="List of appointment prep metadata items (newest first)"
    )
    total: int = Field(description="Total count of appointment preps for this user")
