from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, model_validator


FlowLevel = Literal["spotting", "light", "medium", "heavy"]


class PeriodLogCreate(BaseModel):
    period_start: date
    period_end: Optional[date] = None
    flow_level: Optional[FlowLevel] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_date_order(self) -> "PeriodLogCreate":
        if self.period_end is not None and self.period_end < self.period_start:
            raise ValueError("period_end cannot be before period_start")
        return self


class PeriodLogUpdate(BaseModel):
    period_end: Optional[date] = None
    flow_level: Optional[FlowLevel] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_not_all_none(self) -> "PeriodLogUpdate":
        if self.period_end is None and self.flow_level is None and self.notes is None:
            raise ValueError("At least one field must be provided for update")
        return self


class PeriodLogResponse(BaseModel):
    id: str
    user_id: str
    period_start: date
    period_end: Optional[date] = None
    flow_level: Optional[str] = None
    notes: Optional[str] = None
    cycle_length: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PeriodLogListResponse(BaseModel):
    logs: list[PeriodLogResponse]
    total: int


class CreatePeriodLogResponse(BaseModel):
    log: PeriodLogResponse
    bleeding_alert: bool


class CycleAnalysisResponse(BaseModel):
    average_cycle_length: Optional[float] = None
    cycle_variability: Optional[float] = None
    months_since_last_period: Optional[int] = None
    inferred_stage: Optional[str] = None
    calculated_at: Optional[datetime] = None
    has_sufficient_data: bool = False

    model_config = {"from_attributes": True}
