from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SymptomLogCreate(BaseModel):
    symptoms: list[str] = Field(
        default_factory=list,
        description="Array of symptom tag IDs from symptoms_reference",
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
    symptoms: list[str]
    free_text_entry: str | None
    source: str

    model_config = {"from_attributes": True}


class SymptomLogList(BaseModel):
    logs: list[SymptomLogResponse]
    count: int
    limit: int
