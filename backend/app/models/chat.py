from typing import Literal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class ResponseSection(BaseModel):
    """A paragraph drawn from exactly ONE source."""

    heading: str | None = None
    body: str = Field(
        description=(
            "A conversational paragraph drawn ONLY from the single source referenced "
            "by source_index. Plain text, no markdown formatting. "
            "Write in Meno's voice: warm, direct, evidence-informed, human."
        )
    )
    source_index: int | None = Field(
        default=None,
        description=(
            "The 1-based index of the single source this section draws from. "
            "null only for the closing/disclaimer section."
        ),
    )


class StructuredLLMResponse(BaseModel):
    """Complete structured response from the LLM (v2 paragraph-based schema)."""

    sections: list[ResponseSection] = Field(default_factory=list)
    disclaimer: str | None = None
    insufficient_sources: bool = False


class Citation(BaseModel):
    url: str
    title: str
    section: str | None = None  # e.g., "Perimenopause Overview", "HRT Safety"
    source_index: int | None = (
        None  # 1, 2, 3, etc. for distinguishing same URL different sections
    )


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


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display."""

    id: UUID
    title: str  # First 50 chars of first user message; "New conversation" if empty
    created_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    """Response for listing conversations with pagination."""

    conversations: list[ConversationSummary]
    total: int
    has_more: bool
    limit: int
    offset: int


class ConversationMessagesResponse(BaseModel):
    """Response for loading a specific conversation's messages."""

    conversation_id: UUID
    messages: list[ChatMessage]


class SuggestedPromptsResponse(BaseModel):
    """Response for personalized starter prompts."""

    prompts: list[str]
