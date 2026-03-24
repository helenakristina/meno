"""Service for building system prompts with dynamic context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.llm.system_prompts import (
    LAYER_1_IDENTITY,
    LAYER_2_VOICE,
    LAYER_3_SOURCE_RULES,
    LAYER_4_SCOPE,
)

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
        cycle_context: Optional[dict] = None,
        has_uterus: Optional[bool] = None,
        medication_context: Optional[MedicationContext] = None,
    ) -> str:
        """Assemble the four-layer system prompt with dynamic user context and RAG sources.

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
        age_str = str(age) if age is not None else "unknown"

        source_lines = []
        for i, chunk in enumerate(chunks, start=1):
            url = chunk.get("source_url", "")
            title = chunk.get("title", "").strip()
            content = chunk.get("content", "").strip()
            source_lines.append(f"(Source {i}) {title}\nURL: {url}\nContent: {content}")
        source_count = len(chunks)
        sources_block = (
            "\n\n".join(source_lines)
            if source_lines
            else "No source documents available."
        )

        cycle_lines = []
        if has_uterus is not None:
            cycle_lines.append(f"- Has uterus: {'yes' if has_uterus else 'no'}")
        if cycle_context:
            if cycle_context.get("average_cycle_length") is not None:
                cycle_lines.append(
                    f"- Average cycle length: {cycle_context['average_cycle_length']:.0f} days"
                )
            if cycle_context.get("months_since_last_period") is not None:
                cycle_lines.append(
                    f"- Months since last period: {cycle_context['months_since_last_period']}"
                )
            if cycle_context.get("inferred_stage"):
                cycle_lines.append(
                    f"- Inferred stage from cycle data: {cycle_context['inferred_stage']}"
                )
        cycle_block = ("\n" + "\n".join(cycle_lines)) if cycle_lines else ""

        med_block = ""
        if medication_context:
            med_lines = []
            if medication_context.current_medications:
                for med in medication_context.current_medications:
                    parts = [
                        f"  - {med.medication_name} {med.dose} ({med.delivery_method})"
                    ]
                    if med.frequency:
                        parts[0] += f" — {med.frequency}"
                    if med.start_date:
                        parts[0] += f", started {med.start_date}"
                    med_lines.extend(parts)
                med_block += "\n- Current MHT medications:\n" + "\n".join(med_lines)
            if medication_context.recent_changes:
                change_lines = []
                for med in medication_context.recent_changes:
                    change_lines.append(
                        f"  - {med.medication_name} {med.dose} ({med.delivery_method})"
                        f", stopped {med.end_date}"
                    )
                med_block += "\n- Recently stopped MHT medications:\n" + "\n".join(
                    change_lines
                )

        layer_4 = (
            f"User context:\n"
            f"- Journey stage: {journey_stage}\n"
            f"- Age: {age_str}\n"
            f"- Recent symptom summary: {symptom_summary}"
            f"{cycle_block}"
            f"{med_block}\n\n"
            f"Source documents — there are exactly {source_count} source(s). "
            f"Only cite [Source 1] through [Source {source_count}]:\n\n{sources_block}"
        )

        return "\n\n".join(
            [
                LAYER_1_IDENTITY,
                LAYER_2_VOICE,
                LAYER_3_SOURCE_RULES,
                LAYER_4_SCOPE,
                layer_4,
            ]
        )
