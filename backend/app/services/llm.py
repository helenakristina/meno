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
        urgent_symptom: str | None = None,
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
            # Build urgent symptom emphasis if provided
            urgent_lead = ""
            if urgent_symptom:
                urgent_lead = f"Patient's urgent concern: {urgent_symptom}. "

            user_prompt = (
                f"Write a brief clinical summary for a healthcare provider seeing this patient.\n\n"
                f"CRITICAL: Only use information provided below. Do NOT invent or assume anything.\n"
                f"Do NOT make recommendations. Describe the picture, let provider decide.\n\n"
                f"Patient Data:\n"
                f"- Age: {age_str}\n"
                f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
                f"- Goal: {goal.replace('_', ' ')}\n"
                f"- Urgent Concern: {urgent_symptom if urgent_symptom else 'None specified'}\n"
                f"- Narrative Summary: {narrative}\n"
                f"- Concerns: {concerns_text}\n\n"
                f"{urgent_lead}\n\n"
                f"Structure:\n\n"
                f"1. OPENING (2-3 sentences)\n"
                f"   - Who: Patient age, menopausal stage (extract from narrative)\n"
                f"   - Why: Goal for appointment\n"
                f"   - Urgent: If provided, mention urgent concern\n"
                f"   - Example: 'Jane is a 50-year-old in late perimenopause presenting for evaluation. "\
                f"Her urgent concern is hot flashes, which she reports are occurring 16 times in the past 60 days "\
                f"and significantly affecting her work. She's interested in understanding her options.'\n\n"
                f"2. SYMPTOM PICTURE (3-4 sentences)\n"
                f"   - Extract key symptoms from narrative (only what's there)\n"
                f"   - Use actual frequencies from narrative\n"
                f"   - Describe impact on function\n"
                f"   - Do NOT add symptoms not in narrative\n"
                f"   - Example: 'Logs show 16 hot flash episodes in 60 days, 11 night sweats, and 10 instances "\
                f"of insomnia. She reports sleep disruption is impacting her cognitive function during the day.'\n\n"
                f"3. KEY PATTERNS (2-3 sentences, only if narrative mentions them)\n"
                f"   - Co-occurrence patterns explicitly mentioned in narrative\n"
                f"   - Do NOT invent connections\n"
                f"   - Example: 'Her logs show difficulty concentrating consistently co-occurs with frequent "\
                f"nighttime waking, suggesting sleep disruption is driving cognitive symptoms.'\n\n"
                f"4. PRIORITIZED CONCERNS (bulleted, as provided)\n"
                f"   - Use exact concerns from the list provided\n"
                f"   - Do NOT add, remove, or reorder concerns\n"
                f"   - Do NOT comment on or interpret them\n\n"
                f"5. CLOSING (1-2 sentences)\n"
                f"   - Brief statement of what patient is seeking\n"
                f"   - Do NOT make recommendations\n"
                f"   - Example: 'Patient is well-informed and motivated. She's seeking discussion of her options "\
                f"for the symptom picture described.'\n\n"
                f"CRITICAL RULES:\n"
                f"- If urgent symptom provided: Lead with it, make it central\n"
                f"- Use only data provided (narrative, concerns list, goals)\n"
                f"- Do NOT invent symptoms, frequencies, or patterns\n"
                f"- Do NOT suggest treatments or tests\n"
                f"- Do NOT add psychological interpretation\n"
                f"- Do NOT make assumptions about root causes\n\n"
                f"Tone: Conversational clinical. Busy provider reading in 2 minutes.\n"
                f"Length: Maximum 2 pages."
            )
        else:  # personal_cheatsheet
            # Build urgent symptom emphasis if provided
            urgent_emphasis = ""
            if urgent_symptom:
                urgent_emphasis = (
                    f"\nURGENT SYMPTOM: {urgent_symptom}\n"
                    f"This is your primary concern for this appointment. Make sure it's the focus of your conversation."
                )

            user_prompt = (
                f"Write a personal preparation document for a patient's healthcare appointment.\n"
                f"This is HER working document—concise, actionable, no fluff.\n\n"
                f"CRITICAL: Only use information provided below. Do NOT invent or assume content.\n"
                f"Do NOT suggest treatments or medications. Do NOT add context that wasn't provided.\n\n"
                f"Patient Data:\n"
                f"- Age: {age_str}\n"
                f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
                f"- Primary Goal: {goal.replace('_', ' ')}\n"
                f"- Urgent Concern: {urgent_symptom if urgent_symptom else 'None specified'}\n"
                f"- Symptoms Logged: {', '.join([s.split('(')[0].strip() for s in narrative.split(chr(10)) if '(' in s][:5]) if narrative else 'See narrative below'}\n"
                f"- Prioritized Concerns: {concerns_text}\n"
                f"- Narrative Summary: {narrative}\n"
                f"{urgent_emphasis}\n\n"
                f"Structure:\n\n"
                f"1. OPENING STATEMENT (2-3 sentences)\n"
                f"   - Start with age and menopause stage (from narrative)\n"
                f"   - Lead with urgent symptom if provided\n"
                f"   - State goal\n"
                f"   - Example: 'I am 50 and in late perimenopause. My urgent concern is hot flashes, "\
                f"which are significantly affecting my daily life. I'm here today to understand my options.'\n\n"
                f"2. SYMPTOMS RANKED BY IMPACT\n"
                f"   - IF urgent symptom is provided: Make it #1, describe impact, provide suggested language\n"
                f"   - Then add other concerns from the prioritized list (in order provided)\n"
                f"   - For each symptom, include:\n"
                f"     * Name and frequency (from narrative if available)\n"
                f"     * Impact on daily life\n"
                f"     * What to say in appointment\n"
                f"   - Do NOT add symptoms not mentioned in data\n\n"
                f"3. KEY CONCERNS (bulleted)\n"
                f"   - Use ONLY the concerns provided in the prioritized list\n"
                f"   - Do NOT invent additional concerns\n"
                f"   - Do NOT suggest treatments\n\n"
                f"4. QUESTIONS TO ASK (grouped by topic)\n"
                f"   - Questions about the urgent symptom (if provided)\n"
                f"   - Questions about other concerns (if any)\n"
                f"   - Questions about monitoring/tracking\n"
                f"   - Keep questions open-ended, not leading\n\n"
                f"5. 'IF THINGS GO SIDEWAYS' (only if she mentioned past dismissal)\n"
                f"   - Common dismissals she might hear\n"
                f"   - Evidence-based responses\n"
                f"   - Do NOT invent dismissal scenarios\n\n"
                f"6. WHAT TO BRING\n"
                f"   - Symptom tracking log\n"
                f"   - Current medications/supplements\n"
                f"   - Relevant medical history\n"
                f"   - Recent labs\n\n"
                f"CRITICAL RULES:\n"
                f"- If no urgent symptom: Make first concern from list the focus\n"
                f"- If urgent symptom provided: Make it #1 and emphasize it throughout\n"
                f"- Only reference symptoms/concerns that are actually in the data\n"
                f"- Do NOT suggest treatments ('start hormone therapy', 'try this medication', etc.)\n"
                f"- Do NOT invent context ('you probably also have...' or 'you likely experience...')\n"
                f"- Do NOT add emotional language or encouragement\n\n"
                f"Tone: Professional, concise, working document. No motivation speeches or platitudes.\n"
                f"Length: 2-3 pages maximum."
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
