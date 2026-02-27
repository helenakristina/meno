from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    url: str
    title: str
    section: str | None = None  # e.g., "Perimenopause Overview", "HRT Safety"
    source_index: int | None = None  # 1, 2, 3, etc. for distinguishing same URL different sections


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(description="The user's question")
    conversation_id: UUID | None = Field(
        default=None,
        description="Existing conversation UUID to append to; omit to start a new conversation",
    )


class ChatResponse(BaseModel):
    message: str
    citations: list[Citation]
    conversation_id: UUID
