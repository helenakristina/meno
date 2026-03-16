from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.providers import InsuranceType

JourneyStage = Literal["perimenopause", "menopause", "post-menopause", "unsure"]


class UserProfile(BaseModel):
    """Full user profile row from the users table."""

    id: str
    email: str
    date_of_birth: date | None = None
    journey_stage: str | None = None
    insurance_type: str | None = None
    insurance_plan_name: str | None = None
    onboarding_completed: bool = False
    period_tracking_enabled: bool = True
    has_uterus: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OnboardingRequest(BaseModel):
    date_of_birth: date = Field(description="User's date of birth (YYYY-MM-DD)")
    journey_stage: JourneyStage = Field(
        description="User's self-reported menopause journey stage"
    )


class UserResponse(BaseModel):
    id: str
    email: str
    date_of_birth: date
    journey_stage: str
    onboarding_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InsurancePreference(BaseModel):
    insurance_type: InsuranceType | None
    insurance_plan_name: str | None


class InsurancePreferenceUpdate(BaseModel):
    insurance_type: InsuranceType
    insurance_plan_name: str | None = None


class UserSettingsResponse(BaseModel):
    period_tracking_enabled: bool
    has_uterus: bool | None
    journey_stage: str | None


class UserSettingsUpdate(BaseModel):
    period_tracking_enabled: bool | None = None
    has_uterus: bool | None = None
    journey_stage: JourneyStage | None = None
