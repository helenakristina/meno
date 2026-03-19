"""Pydantic models for MHT medication tracking."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

DeliveryMethod = Literal[
    "patch", "pill", "gel", "cream", "ring",
    "injection", "pellet", "spray", "troche",
    "sublingual", "other",
]

HormoneType = Literal[
    "estrogen", "progesterone", "progestin", "testosterone", "combination"
]

ChangeDirection = Literal["improved", "worsened", "stable"]


# ---------------------------------------------------------------------------
# Reference table models
# ---------------------------------------------------------------------------

class MedicationReferenceResult(BaseModel):
    """A medications_reference row returned from search."""

    id: str
    brand_name: Optional[str] = None
    generic_name: str
    hormone_type: HormoneType
    common_forms: list[str] = Field(default_factory=list)
    common_doses: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    is_user_created: bool = False

    model_config = {"from_attributes": True}


class MedicationReferenceCreate(BaseModel):
    """Payload for creating a user-created medications_reference entry."""

    generic_name: str = Field(min_length=1, max_length=200)
    brand_name: Optional[str] = Field(default=None, max_length=200)
    hormone_type: HormoneType
    common_forms: list[DeliveryMethod] = Field(default_factory=list)
    common_doses: list[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# user_medications models
# ---------------------------------------------------------------------------

class MedicationCreate(BaseModel):
    """Payload for adding a new medication stint."""

    medication_ref_id: Optional[str] = None
    medication_name: str = Field(min_length=1, max_length=200)
    dose: str = Field(min_length=1, max_length=100)
    delivery_method: DeliveryMethod
    frequency: Optional[str] = Field(default=None, max_length=100)
    start_date: date
    notes: Optional[str] = Field(default=None, max_length=1000)


class MedicationUpdate(BaseModel):
    """Payload for updating a medication stint (notes and end_date only).

    Dose and delivery method changes must use the change-dose flow
    (POST /medications/{id}/change) to preserve timeline integrity.
    """

    end_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_not_all_none(self) -> "MedicationUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class MedicationChangeDose(BaseModel):
    """Payload for the atomic dose/method change flow."""

    effective_date: date
    dose: str = Field(min_length=1, max_length=100)
    delivery_method: DeliveryMethod
    frequency: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MedicationResponse(BaseModel):
    """A user_medications row returned from the API."""

    id: str
    medication_ref_id: Optional[str] = None
    medication_name: str
    dose: str
    delivery_method: DeliveryMethod
    frequency: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    previous_entry_id: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class MedicationChangeDoseResponse(BaseModel):
    """Response from the dose-change endpoint."""

    new_medication_id: str
    previous_medication_id: str


# ---------------------------------------------------------------------------
# Before/after symptom comparison models
# ---------------------------------------------------------------------------

class SymptomComparisonRow(BaseModel):
    """One symptom's data in the before/after comparison."""

    symptom_id: str
    symptom_name: str
    category: str
    before_count: int
    before_days: int
    before_pct: float           # 0.0–100.0
    after_count: int
    after_days: int
    after_pct: float            # 0.0–100.0
    direction: ChangeDirection  # "improved" | "worsened" | "stable"


class SymptomComparisonResponse(BaseModel):
    """Full before/after symptom comparison for one medication stint."""

    medication_id: str
    medication_name: str
    dose: str
    delivery_method: str
    start_date: date
    end_date: Optional[date] = None

    # Window used for the comparison
    before_start: Optional[date] = None
    before_end: Optional[date] = None
    after_start: Optional[date] = None
    after_end: Optional[date] = None
    window_days: int = 0

    has_after_data: bool = True
    before_log_days: int = 0        # actual days with symptom logs in before window
    after_log_days: int = 0         # actual days with symptom logs in after window
    before_is_sparse: bool = False  # fewer than 14 days of log data
    after_is_sparse: bool = False

    rows: list[SymptomComparisonRow] = Field(default_factory=list)

    # True if other medication events fall within either comparison window
    has_confounding_changes: bool = False


# ---------------------------------------------------------------------------
# Context models (used by integration consumers)
# ---------------------------------------------------------------------------

class MedicationContext(BaseModel):
    """Medication context injected into LLM prompts (Ask Meno, Appointment Prep)."""

    current_medications: list[MedicationResponse] = Field(default_factory=list)
    recent_changes: list[MedicationResponse] = Field(default_factory=list)  # stopped in last 90 days
