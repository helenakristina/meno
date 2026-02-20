from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    url: str
    title: str


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
