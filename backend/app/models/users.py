from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.providers import InsuranceType

JourneyStage = Literal["perimenopause", "menopause", "post-menopause", "unsure"]


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
