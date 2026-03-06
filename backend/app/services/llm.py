"""LLM service for generating symptom summaries and provider questions.

Uses dependency injection to accept any LLMProvider (OpenAI, Claude, etc.).
All prompts use "logs show" language and never diagnose, prescribe, or recommend
specific treatments. See CLAUDE.md for the LLM provider migration strategy.
"""
import logging
from datetime import date

from app.models.symptoms import SymptomFrequency, SymptomPair
from app.services.llm_base import LLMProvider

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

        freq_lines = [
            f"- {s.symptom_name} ({s.category}): logged {s.count} time(s)"
            for s in frequency_stats[:10]
        ]
        freq_text = "\n".join(freq_lines) if freq_lines else "No symptom data available."

        coocc_lines = [
            f"- {p.symptom1_name} + {p.symptom2_name}: "
            f"co-occurred {p.cooccurrence_count} time(s) "
            f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
            for p in cooccurrence_stats[:5]
        ]
        coocc_text = (
            "\n".join(coocc_lines) if coocc_lines else "No notable co-occurrence patterns."
        )

        system_prompt = (
            "You are a clinical data summarizer preparing a symptom log report for a "
            "healthcare provider visit. Your role is to present objective patterns from "
            "personal symptom tracking data — not to diagnose, interpret medical causes, "
            "or recommend treatments.\n\n"
            "Rules:\n"
            "- Always use 'logs show' or 'data indicates' — never 'you have' or 'you are experiencing'\n"
            "- Never suggest a diagnosis, medical condition, or cause\n"
            "- Never recommend any medication, supplement, or treatment\n"
            "- Frame all observations as patterns worth discussing with a provider\n"
            "- Professional, neutral, clinical tone\n"
            "- Exactly 2–3 paragraphs\n"
            "- End with one sentence noting these patterns are worth discussing with a provider"
        )

        user_prompt = (
            f"Write a 2–3 paragraph clinical summary of the following symptom tracking "
            f"data for a provider report. The data covers "
            f"{start.strftime('%B %d, %Y')} to {end.strftime('%B %d, %Y')}.\n\n"
            f"Most frequently logged symptoms:\n{freq_text}\n\n"
            f"Symptom co-occurrence patterns:\n{coocc_text}\n\n"
            "Write a clear, objective summary for a healthcare provider. "
            "Use 'logs show' language throughout. No diagnoses. No treatment recommendations."
        )

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
        freq_lines = [
            f"- {s.symptom_name}: logged {s.count} time(s)" for s in frequency_stats[:10]
        ]
        freq_text = "\n".join(freq_lines) if freq_lines else "No symptom data."

        coocc_lines = [
            f"- {p.symptom1_name} and {p.symptom2_name} co-occurred {p.cooccurrence_count} time(s)"
            for p in cooccurrence_stats[:5]
        ]
        coocc_text = (
            "\n".join(coocc_lines) if coocc_lines else "No notable co-occurrence patterns."
        )

        system_prompt = (
            "You are helping someone prepare thoughtful, information-gathering questions "
            "to ask their healthcare provider about symptoms they have been tracking.\n\n"
            "Rules:\n"
            "- Generate exactly 5–7 questions, numbered 1 through 5–7\n"
            "- Questions gather information and understanding — not treatments\n"
            "- Start each question with: 'Could you help me understand...', "
            "'What might explain...', 'I've noticed that... could you tell me more about...', "
            "or 'How might... relate to...'\n"
            "- Never use 'Should I take', 'Do I need', or 'Should I stop'\n"
            "- Never mention specific medications by name\n"
            "- Never ask for a diagnosis\n"
            "- Write in first person as if the patient is asking\n"
            "- Return ONLY a numbered list, one question per line (e.g. '1. Could you help...')\n"
            "- No introduction, no conclusion, no headers — just the numbered questions"
        )

        context_section = f"\nAdditional context: {user_context}" if user_context else ""
        user_prompt = (
            f"Based on the following symptom tracking data, generate 5–7 questions "
            f"this person might ask their healthcare provider.\n\n"
            f"Frequently logged symptoms:\n{freq_text}\n\n"
            f"Symptoms that occurred together:\n{coocc_text}"
            f"{context_section}\n\n"
            "Return a numbered list of 5–7 information-gathering questions. "
            "Start each with 'Could you help me understand', 'What might explain', or similar. "
            "No specific medications. No diagnosis requests."
        )

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
            goal: Appointment goal (understand_where_i_am, discuss_starting_hrt, etc.).
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

        system_prompt = (
            "You are helping someone practice responses to dismissive comments from healthcare providers. "
            "Your suggestions are grounded, assertive, and focus on self-advocacy without being confrontational.\n\n"
            "Rules:\n"
            "- Generate realistic, assertive response suggestions\n"
            "- Never recommend medical advice or specific treatments\n"
            "- Focus on self-advocacy, data presentation, and boundary-setting\n"
            "- Keep responses concise and suitable for an actual conversation\n"
            "- Return ONLY a valid JSON array with no markdown, no explanation\n"
            "- Each object must have: {\"scenario_title\": string, \"suggestion\": string}"
        )

        user_prompt = (
            f"Generate suggestions for practicing responses to these dismissal scenarios:\n{scenarios_text}\n\n"
            f"User context:\n"
            f"- Appointment type: {appointment_type.replace('_', ' ')}\n"
            f"- Goal: {goal.replace('_', ' ')}\n"
            f"- Prior dismissal experience: {dismissed_before.replace('_', ' ')}\n"
            f"- Age: {age_str}\n"
            f"- Prioritized concerns: {concerns_text}\n\n"
            "Return a JSON array where each scenario gets a suggested response:\n"
            "[{\"scenario_title\": \"...\", \"suggestion\": \"...\"}, ...]"
        )

        logger.info(
            "Generating scenario suggestions: count=%d",
            len(scenarios_to_generate),
        )

        raw = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=800,
            temperature=0.5,
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
    ) -> str:
        """Generate markdown content for PDF outputs.

        Produces either a provider-facing summary or personal cheat sheet.

        Args:
            content_type: "provider_summary" or "personal_cheatsheet".
            narrative: The LLM-generated narrative from Step 2.
            concerns: User's prioritized concerns from Step 3.
            appointment_type: Type of appointment (new_provider or established_relationship).
            goal: Appointment goal (understand_where_i_am, discuss_starting_hrt, etc.).
            user_age: User's age in years (optional).

        Returns:
            Markdown string suitable for PDF conversion.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        concerns_text = "\n".join([f"- {c}" for c in concerns])
        age_str = str(user_age) if user_age else "not specified"

        if content_type == "provider_summary":
            system_prompt = (
                "You are creating a professional one-page clinical summary for a healthcare provider. "
                "This document will be printed and given to or discussed with the provider.\n\n"
                "Requirements:\n"
                "- Professional tone, suitable for a medical setting\n"
                "- Use 'logs show' and 'data indicates' language\n"
                "- Never diagnose, suggest causes, or recommend treatments\n"
                "- Include the symptom narrative and prioritized concerns\n"
                "- Structure: Title, Patient Context, Symptom Summary, Key Concerns, Conclusion\n"
                "- Use markdown formatting (# ## - * for structure)\n"
                "- Keep to ~1–2 pages of markdown"
            )
            user_prompt = (
                f"Create a professional provider summary with this information:\n\n"
                f"**Symptom Narrative:**\n{narrative}\n\n"
                f"**Prioritized Concerns:**\n{concerns_text}\n\n"
                f"**Patient Context:**\n"
                f"- Appointment type: {appointment_type.replace('_', ' ')}\n"
                f"- Goal: {goal.replace('_', ' ')}\n"
                f"- Age: {age_str}\n\n"
                "Generate a professional one-page summary in markdown format. "
                "Use 'logs show' language. No diagnoses or treatment recommendations."
            )
        else:  # personal_cheatsheet
            system_prompt = (
                "You are creating a personal reference document for a patient to use during a healthcare appointment. "
                "This is private and can use more conversational language.\n\n"
                "Requirements:\n"
                "- Personal, empowering tone\n"
                "- Lists key concerns in order of priority\n"
                "- Includes talking points and questions\n"
                "- Acknowledges the frustration of dismissal (if applicable)\n"
                "- Provides concrete phrases to use ('I need...' 'Can we...' 'I've been tracking...')\n"
                "- Use markdown formatting (# ## - * for structure)\n"
                "- Keep to 1–2 pages of markdown"
            )
            user_prompt = (
                f"Create a personal cheat sheet for an appointment with this information:\n\n"
                f"**Symptom Summary:**\n{narrative}\n\n"
                f"**Your Top Priorities (in order):**\n{concerns_text}\n\n"
                f"**About This Appointment:**\n"
                f"- Type: {appointment_type.replace('_', ' ')}\n"
                f"- What you want: {goal.replace('_', ' ')}\n"
                f"- Age: {age_str}\n\n"
                "Generate a personal, empowering cheat sheet in markdown. "
                "Include concrete phrases to use. Focus on self-advocacy and data presentation."
            )

        logger.info("Generating PDF content: type=%s", content_type)

        content = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1200,
            temperature=0.6,
        )

        logger.info("PDF content generated: type=%s length=%d", content_type, len(content))
        return content
