"""Context block builder for LLM system prompts.

Owns all formatting of the dynamic Layer 5 context block. Takes raw data
objects as inputs, returns a formatted string ready for prompt assembly in
PromptService.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.sanitize import sanitize_prompt_input

if TYPE_CHECKING:
    from app.models.medications import MedicationContext


class ContextBuilder:
    """Builds the dynamic Layer 5 context block for Ask Meno system prompts."""

    @staticmethod
    def build(
        journey_stage: str,
        age: int | None,
        symptom_summary: str,
        chunks: list[dict],
        cycle_context: dict | None = None,
        has_uterus: bool | None = None,
        medication_context: MedicationContext | None = None,
    ) -> str:
        """Assemble the dynamic user context block for LLM prompt Layer 5.

        Args:
            journey_stage: User's menopause journey stage.
            age: User's age, or None if not provided.
            symptom_summary: Cached summary of recent symptoms from the database.
            chunks: RAG-retrieved document chunks with metadata.
            cycle_context: Optional dict with cycle analysis fields.
            has_uterus: Whether the user has a uterus, or None if not set.
            medication_context: Optional MHT medication context for LLM injection.

        Returns:
            Formatted context string ready to be used as the fifth layer of the
            system prompt.
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
                    name = sanitize_prompt_input(med.medication_name, max_length=100)
                    dose = sanitize_prompt_input(med.dose, max_length=50)
                    method = sanitize_prompt_input(med.delivery_method, max_length=50)
                    parts = [f"  - {name} {dose} ({method})"]
                    if med.frequency:
                        parts[0] += (
                            f" — {sanitize_prompt_input(med.frequency, max_length=50)}"
                        )
                    if med.start_date:
                        parts[0] += f", started {med.start_date}"
                    med_lines.extend(parts)
                med_block += "\n- Current MHT medications:\n" + "\n".join(med_lines)
            if medication_context.recent_changes:
                change_lines = []
                for med in medication_context.recent_changes:
                    name = sanitize_prompt_input(med.medication_name, max_length=100)
                    dose = sanitize_prompt_input(med.dose, max_length=50)
                    method = sanitize_prompt_input(med.delivery_method, max_length=50)
                    end = (
                        sanitize_prompt_input(med.end_date, max_length=50)
                        if isinstance(med.end_date, str)
                        else med.end_date
                    )
                    change_lines.append(f"  - {name} {dose} ({method}), stopped {end}")
                med_block += "\n- Recently stopped MHT medications:\n" + "\n".join(
                    change_lines
                )

        return (
            f"User context:\n"
            f"- Journey stage: {journey_stage}\n"
            f"- Age: {age_str}\n"
            f"- Recent symptom summary: {sanitize_prompt_input(symptom_summary, max_length=500)}"
            f"{cycle_block}"
            f"{med_block}\n\n"
            f"Source documents — there are exactly {source_count} source(s). "
            f"Only cite [Source 1] through [Source {source_count}]:\n\n{sources_block}"
        )
