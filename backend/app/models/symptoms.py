from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SymptomDetail(BaseModel):
    id: str
    name: str
    category: str


class SymptomLogCreate(BaseModel):
    # UUIDs from symptoms_reference.id — validated against the table on create.
    symptoms: list[str] = Field(
        default_factory=list,
        description="Array of symptom UUIDs from symptoms_reference.id",
    )
    free_text_entry: str | None = Field(
        default=None,
        description="Free-text notes in the user's own words",
    )
    source: Literal["cards", "text", "both"] = Field(
        description="How the log was created: via cards, free text, or both",
    )
    logged_at: datetime | None = Field(
        default=None,
        description="Timestamp for the log entry; defaults to NOW() if omitted",
    )

    @model_validator(mode="after")
    def validate_content(self) -> "SymptomLogCreate":
        if self.source in ("cards", "both") and not self.symptoms:
            raise ValueError(
                "symptoms cannot be empty when source is 'cards' or 'both'"
            )
        if self.source in ("text", "both") and not self.free_text_entry:
            raise ValueError(
                "free_text_entry cannot be empty when source is 'text' or 'both'"
            )
        return self


class SymptomLogResponse(BaseModel):
    id: str
    user_id: str
    logged_at: datetime
    symptoms: list[SymptomDetail]
    free_text_entry: str | None
    source: str


class SymptomLogList(BaseModel):
    logs: list[SymptomLogResponse]
    count: int
    limit: int


class SymptomFrequency(BaseModel):
    symptom_id: str
    symptom_name: str
    category: str
    count: int


class FrequencyStatsResponse(BaseModel):
    stats: list[SymptomFrequency]
    date_range_start: date
    date_range_end: date
    total_logs: int
