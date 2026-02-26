from datetime import date
from enum import Enum

from pydantic import BaseModel


class ProviderCard(BaseModel):
    id: str
    name: str
    credentials: str | None
    practice_name: str | None
    city: str
    state: str
    zip_code: str | None
    phone: str | None
    website: str | None
    nams_certified: bool
    provider_type: str | None
    specialties: list[str]
    insurance_accepted: list[str]
    data_source: str | None
    last_verified: date | None


class ProviderSearchResponse(BaseModel):
    providers: list[ProviderCard]
    total: int
    page: int
    page_size: int
    total_pages: int


class StateCount(BaseModel):
    state: str
    count: int


class InsuranceType(str, Enum):
    private = "private"
    medicare = "medicare"
    medicaid = "medicaid"
    self_pay = "self_pay"
    other = "other"


class CallingScriptRequest(BaseModel):
    provider_id: str
    provider_name: str
    insurance_type: InsuranceType
    insurance_plan_name: str | None = None
    insurance_plan_unknown: bool = False
    interested_in_telehealth: bool = False


class CallingScriptResponse(BaseModel):
    script: str
    provider_name: str


# ---------------------------------------------------------------------------
# Shortlist / Call Tracker models
# ---------------------------------------------------------------------------


class ShortlistStatus(str, Enum):
    to_call = "to_call"
    called = "called"
    left_voicemail = "left_voicemail"
    booking = "booking"
    not_available = "not_available"


class ShortlistEntry(BaseModel):
    id: str
    user_id: str
    provider_id: str
    status: ShortlistStatus
    notes: str | None
    added_at: str
    updated_at: str


class ShortlistEntryWithProvider(ShortlistEntry):
    provider: ProviderCard


class AddToShortlistRequest(BaseModel):
    provider_id: str


class UpdateShortlistRequest(BaseModel):
    # None means "don't update this field". Empty string for notes means "clear notes".
    status: ShortlistStatus | None = None
    notes: str | None = None
