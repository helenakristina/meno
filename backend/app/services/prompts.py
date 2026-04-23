"""Service for building system prompts with dynamic context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.llm.system_prompts import (
    LAYER_1_IDENTITY,
    LAYER_2_VOICE,
    LAYER_3_SOURCE_RULES,
    LAYER_4_SCOPE,
)
from app.utils.context_builder import build_context_block

if TYPE_CHECKING:
    from app.models.medications import MedicationContext


class PromptService:
    """Service for building system prompts with dynamic context."""

    @staticmethod
    def build_system_prompt(
        journey_stage: str,
        age: int | None,
        symptom_summary: str,
        chunks: list[dict],
        cycle_context: dict | None = None,
        has_uterus: bool | None = None,
        medication_context: MedicationContext | None = None,
    ) -> str:
        """Assemble the five-layer system prompt with dynamic user context and RAG sources.

        Args:
            journey_stage: User's menopause journey stage (e.g., "perimenopause", "menopause")
            age: User's age, or None if not provided
            symptom_summary: Cached summary of recent symptoms from database
            chunks: List of RAG-retrieved document chunks with metadata
            cycle_context: Optional dict with cycle analysis fields (average_cycle_length,
                months_since_last_period, inferred_stage)
            has_uterus: Whether the user has a uterus, or None if not set
            medication_context: Optional MHT medication context for LLM injection

        Returns:
            Complete five-layer system prompt ready for LLM consumption.
        """
        context_block = build_context_block(
            journey_stage=journey_stage,
            age=age,
            symptom_summary=symptom_summary,
            chunks=chunks,
            cycle_context=cycle_context,
            has_uterus=has_uterus,
            medication_context=medication_context,
        )
        return "\n\n".join(
            [
                LAYER_1_IDENTITY,
                LAYER_2_VOICE,
                LAYER_3_SOURCE_RULES,
                LAYER_4_SCOPE,
                context_block,
            ]
        )
