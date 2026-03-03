"""Service for building system prompts with dynamic context."""

from app.llm.system_prompts import LAYER_1, LAYER_2, LAYER_3


class PromptService:
    """Service for building system prompts with dynamic context."""

    @staticmethod
    def build_system_prompt(
        journey_stage: str,
        age: int | None,
        symptom_summary: str,
        chunks: list[dict],
    ) -> str:
        """Assemble the four-layer system prompt with dynamic user context and RAG sources.

        Args:
            journey_stage: User's menopause journey stage (e.g., "perimenopause", "menopause")
            age: User's age, or None if not provided
            symptom_summary: Cached summary of recent symptoms from database
            chunks: List of RAG-retrieved document chunks with metadata

        Returns:
            Complete four-layer system prompt ready for LLM consumption.
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
            "\n\n".join(source_lines) if source_lines else "No source documents available."
        )

        layer_4 = (
            f"User context:\n"
            f"- Journey stage: {journey_stage}\n"
            f"- Age: {age_str}\n"
            f"- Recent symptom summary: {symptom_summary}\n\n"
            f"Source documents — there are exactly {source_count} source(s). "
            f"Only cite [Source 1] through [Source {source_count}]:\n\n{sources_block}"
        )

        return "\n\n".join([LAYER_1, LAYER_2, LAYER_3, layer_4])
