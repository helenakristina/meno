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

        system_prompt = (
            "You are helping a woman prepare for a healthcare appointment about perimenopause or menopause. "
            "Your role is to help her respond to common dismissals she might encounter from healthcare providers.\n\n"
            "Guidelines:\n"
            "- Ground responses in current evidence and research (NAMS guidelines, peer-reviewed studies, major medical organizations)\n"
            "- Address the specific dismissal directly and acknowledge the provider's perspective\n"
            "- Provide concrete language she can use in the appointment\n"
            "- Reference specific research/statistics when relevant (e.g., 'Research shows...', 'The NAMS guidelines state...')\n"
            "- Never diagnose or prescribe, but DO reference evidence-based information\n"
            "- Empower her to advocate for herself\n"
            "- Acknowledge her experience and validate her concerns\n"
            "- Make responses conversational and natural (2-3 sentences max)\n"
            "- Return ONLY a valid JSON array with no markdown, no explanation\n"
            "- Each object must have: {\"scenario_title\": string, \"suggestion\": string}"
        )

        user_prompt = (
            f"A woman is preparing for an appointment and may encounter these dismissals from her provider:\n\n"
            f"{scenarios_text}\n\n"
            f"Her context:\n"
            f"- Age: {age_str}\n"
            f"- Appointment type: {appointment_type.replace('_', ' ')}\n"
            f"- What she wants to accomplish: {goal.replace('_', ' ')}\n"
            f"- Prior dismissal experience: {dismissed_before.replace('_', ' ')}\n"
            f"- Her top concerns (in order):\n{concerns_text}\n\n"
            f"For EACH dismissal scenario above, generate a response she could use in her appointment. Each response should:\n\n"
            f"1. Acknowledge the provider's perspective/concern\n"
            f"2. Reference relevant evidence or guidelines (be specific—cite research, statistics, organization names like NAMS)\n"
            f"3. Redirect toward evidence-based options for her specific situation\n"
            f"4. Use conversational 'I' statements ('I understand...', 'I've read...', 'Can we...')\n"
            f"5. Be 2-3 sentences MAXIMUM (she needs to say this in an appointment)\n"
            f"6. Empower her to advocate for herself without being confrontational\n\n"
            f"Examples of good responses for perimenopause/menopause:\n"
            f"- \"I understand the concern about breast cancer risk. Recent NAMS research shows the risk varies based on individual factors. Can we discuss which risk factors apply to me?\"\n"
            f"- \"I appreciate your suggestion, but the NAMS guidelines recommend discussing hormone therapy options for my symptoms. Would you be willing to review those with me?\"\n"
            f"- \"I've read that hot flashes aren't just a normal part of aging—they're a treatable medical symptom. What options do you recommend for my situation?\"\n"
            f"- \"I understand wanting to try lifestyle changes, but my symptoms are significantly impacting my quality of life. Can we discuss all available options?\"\n\n"
            f"Return a JSON array with one suggestion per scenario:\n"
            f"[{{\"scenario_title\": \"...\", \"suggestion\": \"...\"}}, ...]"
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
        Both are clinically-grounded, specific to the patient's situation,
        and free of platitudes or generic templates.

        Args:
            content_type: "provider_summary" or "personal_cheatsheet".
            narrative: The LLM-generated narrative from Step 2.
            concerns: User's prioritized concerns from Step 3.
            appointment_type: Type of appointment (new_provider or established_relationship).
            goal: Appointment goal (assess_status, explore_hrt, etc.).
            user_age: User's age in years (optional).

        Returns:
            Markdown string suitable for PDF conversion.

        Raises:
            TimeoutError: If the LLM API times out.
            RuntimeError: If the LLM API returns an error or empty response.
        """
        concerns_text = "\n".join([f"- {c}" for c in concerns])
        age_str = str(user_age) if user_age else "not specified"

        # System prompt used by both content types
        system_prompt = (
            "You are a clinical writing expert specializing in perimenopause and menopause. "
            "Your role is to help women prepare for healthcare appointments by generating "
            "clinically-grounded, specific, actionable documents.\n\n"
            "Style Requirements:\n"
            "- Professional, clinical tone (no platitudes, encouragement, or motivational language)\n"
            "- Specific to perimenopause/menopause (not generic health appointments)\n"
            "- Grounded in current evidence and guidelines (reference research where relevant)\n"
            "- Actionable (user can actually use this language in an appointment)\n"
            "- Prioritized by impact, not frequency\n"
            "- Anticipate common provider dismissals and responses\n"
            "- No phrases like 'Hello Future Me', 'You've got this!', 'Hello Warrior', etc.\n\n"
            "Remember: You're writing for an informed patient who knows her body and deserves to be heard."
        )

        if content_type == "provider_summary":
            user_prompt = (
                f"Write a clinical summary for a healthcare provider based on this patient's appointment prep data.\n\n"
                f"Patient Context:\n"
                f"- Age: {age_str}\n"
                f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
                f"- Goal: {goal.replace('_', ' ')}\n"
                f"- Concerns: {concerns_text}\n"
                f"- Narrative Summary: {narrative}\n\n"
                f"Requirements:\n"
                f"1. OPENING: State the appointment context clearly (age, goal, type of provider visit)\n"
                f"2. SYMPTOM PICTURE: Describe the symptom pattern in clinical language\n"
                f"   - Use 'logs show', 'data indicates' language\n"
                f"   - Highlight severity and impact on daily life/function\n"
                f"   - Reference co-occurrence patterns that suggest systemic issues\n"
                f"3. KEY PATTERNS: Call out meaningful patterns (e.g., sleep disruption affecting cognition, systemic dryness)\n"
                f"4. PRIORITIZED CONCERNS: List in order of impact (not frequency)\n"
                f"5. NO RECOMMENDATIONS: Don't suggest specific treatments—let the provider decide\n"
                f"6. TONE: Professional, data-driven, patient-informed (not patronizing)\n\n"
                f"Length: 2-3 pages maximum. Be specific and clinically useful.\n"
                f"Include only what a provider needs to understand the patient's situation.\n"
                f"No disclaimers needed (patient will add those)."
            )
        else:  # personal_cheatsheet
            user_prompt = (
                f"Write a personal preparation document for a patient attending a healthcare appointment.\n"
                f"This is HER cheat sheet to use during the appointment—help her be informed, confident, and heard.\n\n"
                f"Patient Context:\n"
                f"- Age: {age_str}\n"
                f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
                f"- Goal: {goal.replace('_', ' ')}\n"
                f"- Concerns (prioritized): {concerns_text}\n"
                f"- Narrative Summary: {narrative}\n\n"
                f"Structure (follow this exactly):\n\n"
                f"1. OPENING STATEMENT ('Your Story in 60 Seconds')\n"
                f"   - Write a 2-3 sentence opening she can read or hand to her provider\n"
                f"   - Should establish: her age, stage (perimenopause/menopause), key symptoms, her goal\n"
                f"   - Should sound like HER voice, not generic\n"
                f"   - Example: 'I am 50, in late perimenopause. I have been experiencing significant sleep "\
                f"disruption, hot flashes, and anxiety. My goal today is to discuss hormone therapy options.'\n"
                f"   - NO PLATITUDES\n\n"
                f"2. SYMPTOMS RANKED BY IMPACT\n"
                f"   - List symptoms in order of impact on daily life (not frequency)\n"
                f"   - For each, include: the symptom, its impact, what she wants to discuss\n"
                f"   - Example format:\n"
                f"     '1. Sleep Disruption (5-10 wakings per night)\n"
                f"      Impact: Chronic fatigue, cognitive difficulty, affecting ability to work\n"
                f"      What to say: \"Sleep disruption is my primary concern. Can we discuss what's causing "\
                f"the wakings and how we address it?\"'\n\n"
                f"3. KEY CONCERNS SECTION\n"
                f"   - What she wants to accomplish in this appointment\n"
                f"   - Specific, prioritized, actionable\n"
                f"   - Example: 'I want to discuss starting systemic hormone therapy and understand my options'\n\n"
                f"4. QUESTIONS TO ASK\n"
                f"   - Grouped by topic (on treatment, on her specific symptoms, on monitoring)\n"
                f"   - Clinical questions that show she's informed\n"
                f"   - Example: 'Given my insulin resistance, which estrogen delivery method do you recommend?'\n\n"
                f"5. 'IF THINGS GO SIDEWAYS' SECTION\n"
                f"   - Common dismissals she might hear (based on her goal/situation)\n"
                f"   - Evidence-based response for each\n"
                f"   - Give her language she can actually use\n"
                f"   - Example:\n"
                f"     'If they say: \"HRT increases breast cancer risk\"\n"
                f"      You can say: \"I understand the original WHI concern, but recent evidence shows...\""\
                f"\n      or ask: \"Can you walk me through the current evidence for my specific situation?\"'\n\n"
                f"6. WHAT TO BRING\n"
                f"   - Specific items relevant to her situation\n"
                f"   - Lab results, medication list, relevant history\n\n"
                f"TONE: Professional, informed, empowering. NO motivation, NO encouragement, NO platitudes.\n"
                f"This is a working document, not a pep talk.\n\n"
                f"Length: 2-3 pages. Be specific to her situation, not generic.\n"
                f"Reference her actual symptoms and concerns, not template text."
            )

        logger.info("Generating PDF content: type=%s age=%s goal=%s", content_type, age_str, goal)

        content = await self.provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1500,
            temperature=0.5,
        )

        logger.info("PDF content generated: type=%s length=%d", content_type, len(content))
        return content
