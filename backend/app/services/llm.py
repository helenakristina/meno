"""LLM service for generating symptom summaries and provider questions.

Uses dependency injection to accept any LLMProvider (OpenAI, Claude, etc.).
All prompts use "logs show" language and never diagnose, prescribe, or recommend
specific treatments. See CLAUDE.md for the LLM provider migration strategy.
"""

import logging
from datetime import date

from app.llm.appointment_prompts import (
    CHEATSHEET_SYSTEM,
    PROVIDER_QUESTIONS_SYSTEM,
    PROVIDER_SUMMARY_SYSTEM,
    SCENARIO_SUGGESTIONS_SYSTEM,
    SYMPTOM_SUMMARY_SYSTEM,
    build_cheatsheet_user_prompt,
    build_provider_questions_user_prompt,
    build_provider_summary_user_prompt,
    build_scenario_suggestions_user_prompt,
    build_symptom_summary_user_prompt,
)
from app.models.symptoms import SymptomFrequency, SymptomPair
from app.services.llm_base import LLMProvider
from app.utils.prompt_formatting import (
    format_cooccurrence_stats_for_prompt,
    format_frequency_stats_for_prompt,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service layer for LLM-powered text generation.

    Provides high-level methods for generating summaries, questions, and scripts
    using any LLMProvider implementation. Handles prompt assembly, API calls,
    and response parsing.

    No database access — purely stateless text generation logic.
    """

    def __init__(self, provider: LLMProvider):
        """Initialize with an LLM provider.

        Args:
            provider: An implementation of the LLMProvider protocol (dependency-injected).
        """
        self.provider = provider

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> str:
        """Route a chat completion request through the injected LLM provider.

        All provider calls from services should go through this method so that
        any future cross-cutting concerns (retry logic, rate limiting, token
        caps, provider switching) apply uniformly.

        Args:
            system_prompt: System-level instructions (role, behavior, constraints).
            user_prompt: User's message or query.
            max_tokens: Maximum tokens in the response (1–4096). Defaults to 1024.
            temperature: Sampling temperature (0–2). Defaults to 0.7.
            response_format: Output format hint. "json" for structured JSON output.
                None (default) returns plain text.

        Returns:
            The completed text response from the LLM.

        Raises:
            ValueError: If arguments are invalid.
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        return await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )

    async def generate_narrative(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        """Generate a clinical narrative from pre-assembled prompts.

        Args:
            system_prompt: System instructions (use NARRATIVE_SYSTEM from appointment_prompts).
            user_prompt: Dynamic user prompt (use build_narrative_user_prompt).

        Returns:
            Generated narrative as a plain string.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        logger.info("Generating appointment narrative")
        narrative = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=600,
            temperature=0.3,
        )
        logger.info("Narrative generated: %d characters", len(narrative))
        return narrative

    async def generate_symptom_summary(
        self,
        frequency_stats: list[SymptomFrequency],
        cooccurrence_stats: list[SymptomPair],
        date_range: tuple[date, date],
    ) -> str:
        """Generate a 2–3 paragraph symptom pattern summary for a provider report.

        Frames all observations using "logs show" language. Does not diagnose,
        name medical conditions, or recommend any treatment. Returns the summary
        as a plain string with paragraphs separated by double newlines.

        Args:
            frequency_stats: Symptom occurrence counts, sorted most-frequent first.
            cooccurrence_stats: Symptom pairs sorted by co-occurrence rate.
            date_range: (start, end) dates the logs cover.

        Returns:
            Generated summary text.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        start, end = date_range

        freq_text = format_frequency_stats_for_prompt(frequency_stats)
        coocc_text = format_cooccurrence_stats_for_prompt(cooccurrence_stats)

        system_prompt = SYMPTOM_SUMMARY_SYSTEM
        user_prompt = build_symptom_summary_user_prompt(start, end, freq_text, coocc_text)

        logger.info(
            "Generating symptom summary: range=%s–%s symptoms=%d pairs=%d",
            start,
            end,
            len(frequency_stats),
            len(cooccurrence_stats),
        )

        summary = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=600,
            temperature=0.3,
        )

        logger.info("Symptom summary generated: %d characters", len(summary))
        return summary

    async def generate_provider_questions(
        self,
        frequency_stats: list[SymptomFrequency],
        cooccurrence_stats: list[SymptomPair],
        user_context: str = "",
    ) -> list[str]:
        """Generate 5–7 information-gathering questions for a healthcare provider visit.

        Questions use "Could you help me understand" or "What might explain" framing.
        Never requests specific medications, diagnoses, or treatment plans.

        Args:
            frequency_stats: Symptom occurrence counts, sorted most-frequent first.
            cooccurrence_stats: Symptom pairs sorted by co-occurrence rate.
            user_context: Optional additional context string (e.g. journey stage).

        Returns:
            List of question strings, without leading numbers.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        freq_text = format_frequency_stats_for_prompt(
            frequency_stats, include_category=False, empty_msg="No symptom data."
        )
        coocc_text = format_cooccurrence_stats_for_prompt(
            cooccurrence_stats, verbose=False
        )

        system_prompt = PROVIDER_QUESTIONS_SYSTEM
        user_prompt = build_provider_questions_user_prompt(freq_text, coocc_text, user_context)

        logger.info(
            "Generating provider questions: symptoms=%d pairs=%d",
            len(frequency_stats),
            len(cooccurrence_stats),
        )

        raw = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=500,
            temperature=0.4,
        )

        logger.info("Provider questions generated: %d characters", len(raw))

        questions: list[str] = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip leading "1." / "1)" / "1 " numbering
            if line and line[0].isdigit():
                rest = line.lstrip("0123456789").lstrip(".").lstrip(")").strip()
                if rest:
                    questions.append(rest)
            else:
                questions.append(line)

        return questions[:7]

    async def generate_calling_script(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        """Generate a provider calling script from assembled prompts.

        Args:
            system_prompt: System instructions establishing tone and format.
            user_prompt: User turn with provider name and insurance/needs context.

        Returns:
            The generated script as a plain string, ready to read aloud.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        logger.info("Generating provider calling script")

        script = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=300,
            temperature=0.7,
        )

        logger.info("Calling script generated: %d characters", len(script))
        return script

    async def generate_scenario_suggestions(
        self,
        scenarios_to_generate: list[str],
        concerns: list[str],
        appointment_type: str,
        goal: str,
        dismissed_before: str,
        user_age: int | None,
    ) -> str:
        """Generate LLM suggestions for dismissal scenario responses.

        Returns JSON-formatted scenario suggestions matching the provided scenario titles.

        Args:
            scenarios_to_generate: List of scenario titles (e.g., ["Provider dismisses concerns"]).
            concerns: User's prioritized concerns from Step 3.
            appointment_type: Type of appointment (new_provider or established_relationship).
            goal: Appointment goal (assess_status, explore_hrt, etc.).
            dismissed_before: Prior dismissal experience (no, once_or_twice, multiple_times).
            user_age: User's age in years (optional).

        Returns:
            JSON string with scenario suggestions (parsed by caller).

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        scenarios_text = "\n".join([f"- {s}" for s in scenarios_to_generate])
        concerns_text = "\n".join([f"- {c}" for c in concerns])
        age_str = str(user_age) if user_age else "not specified"

        system_prompt = SCENARIO_SUGGESTIONS_SYSTEM
        user_prompt = build_scenario_suggestions_user_prompt(
            scenarios_text=scenarios_text,
            concerns_text=concerns_text,
            appointment_type=appointment_type,
            goal=goal,
            dismissed_before=dismissed_before,
            age_str=age_str,
        )

        logger.info(
            "Generating scenario suggestions: count=%d",
            len(scenarios_to_generate),
        )

        raw = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1200,
            temperature=0.6,
            response_format="json",
        )

        logger.info("Scenario suggestions generated: %d characters", len(raw))
        return raw

    async def generate_pdf_content(
        self,
        content_type: str,
        narrative: str,
        concerns: list[str],
        appointment_type: str,
        goal: str,
        user_age: int | None,
        urgent_symptom: str | None = None,
        scenarios: list[dict] | None = None,
    ) -> str:
        """Generate markdown content for PDF outputs.

        Produces either a provider-facing summary or personal cheat sheet.
        Both are clinically-grounded, specific to the patient's situation,
        and free of platitudes or generic templates.

        Args:
            content_type: "provider_summary" or "personal_cheatsheet".
            narrative: The LLM-generated narrative from Step 2.
            concerns: User's prioritized concerns from Step 3.
            appointment_type: Type of appointment (new_provider or established_relationship).
            goal: Appointment goal (assess_status, explore_hrt, etc.).
            user_age: User's age in years (optional).
            urgent_symptom: If goal is "urgent_symptom", the specific symptom user selected (optional).
            scenarios: List of scenario cards from Step 4 (optional, used for personal_cheatsheet).
                      Each dict should have: {"title": str, "suggestion": str, "sources": list[str]}.

        Returns:
            Markdown string suitable for PDF conversion.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        concerns_text = "\n".join([f"- {c}" for c in concerns])
        age_str = str(user_age) if user_age else "not specified"

        if content_type == "provider_summary":
            system_prompt = PROVIDER_SUMMARY_SYSTEM
            user_prompt = build_provider_summary_user_prompt(
                narrative=narrative,
                concerns_text=concerns_text,
                appointment_type=appointment_type,
                goal=goal,
                age_str=age_str,
                urgent_symptom=urgent_symptom,
            )
        else:  # personal_cheatsheet
            system_prompt = CHEATSHEET_SYSTEM
            user_prompt = build_cheatsheet_user_prompt(
                narrative=narrative,
                concerns_text=concerns_text,
                appointment_type=appointment_type,
                goal=goal,
                age_str=age_str,
                urgent_symptom=urgent_symptom,
                scenarios=scenarios,
            )

        logger.info(
            "Generating PDF content: type=%s age=%s goal=%s",
            content_type,
            age_str,
            goal,
        )

        content = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1500,
            temperature=0.5,
        )

        logger.info(
            "PDF content generated: type=%s length=%d", content_type, len(content)
        )
        return content
