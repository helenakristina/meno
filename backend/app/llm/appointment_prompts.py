"""System prompt constants and user prompt builders for appointment prep LLM calls.

Six LLM calls in the appointment prep pipeline, each with a constant system prompt
and a builder function for the dynamic user prompt:

  1. NARRATIVE / build_narrative_user_prompt
     → generate_narrative() in appointment.py (Step 2)

  2. SYMPTOM_SUMMARY / build_symptom_summary_user_prompt
     → generate_symptom_summary() in llm.py (used by export flow)

  3. PROVIDER_QUESTIONS / build_provider_questions_user_prompt
     → generate_provider_questions() in llm.py

  4. SCENARIO_SUGGESTIONS / build_scenario_suggestions_user_prompt
     → generate_scenario_suggestions() in llm.py (Step 4)

  5. PROVIDER_SUMMARY / build_provider_summary_user_prompt
     → generate_provider_summary_content() in llm.py (Step 5)

  6. CHEATSHEET / build_cheatsheet_user_prompt
     → generate_cheatsheet_content() in llm.py (Step 5)
"""

from datetime import date

from app.utils.sanitize import sanitize_prompt_input


# ---------------------------------------------------------------------------
# System prompt constants
# ---------------------------------------------------------------------------

NARRATIVE_SYSTEM = (
    "You are preparing a clinical summary of symptom tracking data for a healthcare provider "
    "appointment. Your role is to present objective patterns from personal health tracking — "
    "not to diagnose, interpret causes, or recommend treatments.\n\n"
    "Rules:\n"
    "- Always use 'logs show' or 'data indicates' — never 'you have' or diagnose\n"
    "- Never suggest a medical condition, cause, or specific treatment\n"
    "- Frame observations as patterns worth discussing with a provider\n"
    "- Professional, neutral, clinical tone\n"
    "- Write 2–3 clear paragraphs suitable for a healthcare conversation\n"
    "- End by noting these patterns are worth discussing with a provider"
)

SYMPTOM_SUMMARY_SYSTEM = (
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

PROVIDER_QUESTIONS_SYSTEM = (
    "You are helping someone prepare thoughtful, information-gathering questions "
    "to ask their healthcare provider about symptoms they have been tracking.\n\n"
    "Rules:\n"
    "- Generate exactly 5–7 questions, numbered 1 through 5–7\n"
    "- Questions gather information and understanding — not treatments or diagnoses\n"
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

SCENARIO_SUGGESTIONS_SYSTEM = (
    "You are helping a woman prepare for a healthcare appointment about perimenopause or menopause. "
    "Your role is to help her respond to common dismissals she might encounter from healthcare providers.\n\n"
    "Guidelines:\n"
    "- Use ONLY the provided source documents to ground your responses — do not add external knowledge as citations\n"
    "- Address the specific dismissal directly and acknowledge the provider's perspective\n"
    "- Provide concrete language she can use in the appointment\n"
    "- When sources are provided, reference them specifically (e.g., 'According to [source title]...')\n"
    "- When no sources are provided, use evidence-based language without fabricating citations\n"
    "- Never diagnose or prescribe\n"
    "- Empower her to advocate for herself\n"
    "- Acknowledge her experience and validate her concerns\n"
    "- Make responses conversational and natural (2-3 sentences max)\n"
    "- Return ONLY a valid JSON array with no markdown, no explanation\n"
    '- Each object must have: {"scenario_title": string, "suggestion": string, "sources": [{"title": string, "excerpt": string}]}'
)

PROVIDER_SUMMARY_SYSTEM = (
    "You are a clinical writing expert specializing in perimenopause and menopause. "
    "Your role is to help women prepare for healthcare appointments by generating "
    "clinically-grounded, specific, actionable documents for their providers.\n\n"
    "Style Requirements:\n"
    "- Professional, clinical tone (no platitudes, encouragement, or motivational language)\n"
    "- Specific to perimenopause/menopause (not generic health appointments)\n"
    "- Grounded in current evidence and guidelines (reference research where relevant)\n"
    "- Actionable (provider can use this to have an informed conversation)\n"
    "- Prioritized by impact, not frequency\n"
    "- No phrases like 'Hello Future Me', 'You've got this!', 'Hello Warrior', etc.\n\n"
    "Remember: You're writing for a provider reading a one-page summary before a 15-minute appointment."
)

CHEATSHEET_SYSTEM = (
    "You are a clinical writing expert specializing in perimenopause and menopause. "
    "Your role is to help women prepare for healthcare appointments by generating "
    "clinically-grounded, specific, actionable documents they carry into the room.\n\n"
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


# ---------------------------------------------------------------------------
# Builder functions — dynamic user prompts
# ---------------------------------------------------------------------------


def build_narrative_user_prompt(
    appt_type_str: str,
    goal_str: str,
    age_str: str,
    journey_stage: str,
    days_back: int,
    start_date: date,
    end_date: date,
    freq_text: str,
    coocc_text: str,
    med_section: str,
    what_have_you_tried: str | None = None,
    specific_ask: str | None = None,
) -> str:
    """Build user prompt for clinical narrative generation (Step 2)."""
    # Sanitize user-generated content to prevent prompt injection
    sanitized_tried = sanitize_prompt_input(what_have_you_tried)
    sanitized_ask = sanitize_prompt_input(specific_ask)

    qualitative_section = ""
    if sanitized_tried != "not provided":
        qualitative_section += f"\nWhat the patient has tried: {sanitized_tried}"
    if sanitized_ask != "not provided":
        qualitative_section += (
            f"\nPatient's specific ask for this appointment: {sanitized_ask}"
        )
    return (
        f"Write a 2–3 paragraph clinical summary for a healthcare appointment. "
        f"Patient context: {appt_type_str} appointment, goal is '{goal_str}', "
        f"age {age_str}, journey stage: {journey_stage}. "
        f"Symptom tracking covers {days_back} days "
        f"({start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}).\n\n"
        f"Most frequently logged symptoms:\n{freq_text}\n\n"
        f"Symptom patterns (co-occurrences):\n{coocc_text}"
        f"{med_section}"
        f"{qualitative_section}\n\n"
        "Write a clear, objective summary using 'logs show' language throughout. "
        "No diagnoses. No treatment recommendations."
    )


def build_symptom_summary_user_prompt(
    start: date,
    end: date,
    freq_text: str,
    coocc_text: str,
) -> str:
    """Build user prompt for symptom summary generation (used by export flow)."""
    return (
        f"Write a 2–3 paragraph clinical summary of the following symptom tracking "
        f"data for a provider report. The data covers "
        f"{start.strftime('%B %d, %Y')} to {end.strftime('%B %d, %Y')}.\n\n"
        f"Most frequently logged symptoms:\n{freq_text}\n\n"
        f"Symptom co-occurrence patterns:\n{coocc_text}\n\n"
        "Write a clear, objective summary for a healthcare provider. "
        "Use 'logs show' language throughout. No diagnoses. No treatment recommendations."
    )


def build_provider_questions_user_prompt(
    freq_text: str,
    coocc_text: str,
    user_context: str = "",
) -> str:
    """Build user prompt for provider question generation."""
    # Sanitize user-generated content to prevent prompt injection
    sanitized_context = sanitize_prompt_input(user_context) if user_context else ""
    context_section = (
        f"\nAdditional context: {sanitized_context}"
        if sanitized_context != "not provided"
        else ""
    )
    return (
        f"Based on the following symptom tracking data, generate 5–7 questions "
        f"this person might ask their healthcare provider.\n\n"
        f"Frequently logged symptoms:\n{freq_text}\n\n"
        f"Symptoms that occurred together:\n{coocc_text}"
        f"{context_section}\n\n"
        "Return a numbered list of 5–7 information-gathering questions. "
        "Start each with 'Could you help me understand', 'What might explain', or similar. "
        "No specific medications. No diagnosis requests."
    )


def build_scenario_suggestions_user_prompt(
    scenarios_text: str,
    concerns_text: str,
    appointment_type: str,
    goal: str,
    dismissed_before: str,
    age_str: str,
    rag_chunks: list[dict] | None = None,
) -> str:
    """Build user prompt for scenario suggestion generation (Step 4)."""
    # Sanitize user-generated content to prevent prompt injection
    sanitized_concerns = sanitize_prompt_input(concerns_text)

    sources_section = ""
    if rag_chunks:
        sources_lines = []
        for chunk in rag_chunks:
            title = chunk.get("title", "Source")
            content = chunk.get("content", "")
            sources_lines.append(f"[{title}]: {content}")
        sources_section = (
            "\nSource documents to ground your responses:\n"
            + "\n".join(sources_lines)
            + "\n"
        )

    return (
        f"A woman (age {age_str}) is preparing for a healthcare appointment. "
        f"She may encounter these dismissals specific to her situation:\n\n"
        f"{scenarios_text}\n\n"
        f"Her context:\n"
        f"- Appointment type: {appointment_type.replace('_', ' ')}\n"
        f"- What she's here to discuss: {goal.replace('_', ' ')}\n"
        f"- Prior dismissal experience: {dismissed_before.replace('_', ' ')}\n"
        f"- Her top concerns (in order):\n{sanitized_concerns}"
        f"{sources_section}\n\n"
        f"For EACH dismissal scenario above, generate a confident, evidence-based response "
        f"she can use IN THIS EXACT APPOINTMENT. Requirements:\n\n"
        f"1. Acknowledge the provider's concern (don't dismiss them)\n"
        f"2. Provide evidence-based reasoning (only from the provided sources if available)\n"
        f"3. Redirect to actionable discussion\n"
        f"4. Keep to 2-3 sentences (realistic for appointment)\n"
        f"5. Use conversational 'I' language\n\n"
        f"Return ONLY valid JSON with this exact structure, no markdown or explanation:\n"
        f'{{"scenarios": [{{"scenario_title": "...", "suggestion": "...", "sources": []}}]}}'
    )


def build_provider_summary_user_prompt(
    concerns_text: str,
    appointment_type: str,
    goal: str,
    age_str: str,
    urgent_symptom: str | None = None,
    what_have_you_tried: str | None = None,
    specific_ask: str | None = None,
    history_clotting_risk: str | None = None,
    history_breast_cancer: str | None = None,
) -> str:
    """Build user prompt for provider summary PDF generation (Step 5).

    Requests structured JSON output matching ProviderSummaryResponse.
    """
    # Sanitize user-generated content to prevent prompt injection
    sanitized_concerns = sanitize_prompt_input(concerns_text)
    sanitized_urgent = sanitize_prompt_input(urgent_symptom)
    sanitized_tried = sanitize_prompt_input(what_have_you_tried)
    sanitized_ask = sanitize_prompt_input(specific_ask)

    urgent_line = (
        f"- Urgent Concern: {sanitized_urgent}\n"
        if sanitized_urgent != "not provided"
        else ""
    )
    tried_line = (
        f"- What she has tried: {sanitized_tried}\n"
        if sanitized_tried != "not provided"
        else ""
    )
    ask_line = (
        f"- Specific ask for this appointment: {sanitized_ask}\n"
        if sanitized_ask != "not provided"
        else ""
    )
    clotting_line = (
        f"- History of clotting risk: {history_clotting_risk}\n"
        if history_clotting_risk == "yes"
        else ""
    )
    breast_cancer_line = (
        f"- History of breast cancer risk: {history_breast_cancer}\n"
        if history_breast_cancer == "yes"
        else ""
    )

    return (
        f"Write a clinical appointment summary for a healthcare provider.\n"
        f"The provider will read this in 2 minutes — be specific, scannable, useful.\n\n"
        f"CRITICAL: Only describe what's in the data below. Do NOT invent symptoms, "
        f"frequencies, or connections. No recommendations. No speculation.\n\n"
        f"Patient Data:\n"
        f"- Age: {age_str}\n"
        f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
        f"- Goal: {goal.replace('_', ' ')}\n"
        f"{urgent_line}"
        f"{tried_line}"
        f"{ask_line}"
        f"{clotting_line}"
        f"{breast_cancer_line}"
        f"- Concerns List: {sanitized_concerns}\n\n"
        f"Return ONLY a valid JSON object with exactly these three fields:\n"
        f'{{"opening": "2-3 sentence intro: who, why here, urgent concern if any", '
        f'"key_patterns": "2-3 sentences on co-occurring patterns if present, else empty string", '
        f'"closing": "1-2 sentences on what the patient is seeking from this appointment"}}\n\n'
        f"No markdown. No explanation. No extra fields. Valid JSON only."
    )


def build_cheatsheet_user_prompt(
    narrative: str,
    concerns_text: str,
    appointment_type: str,
    goal: str,
    age_str: str,
    urgent_symptom: str | None = None,
    scenarios: list[dict] | None = None,
    specific_ask: str | None = None,
) -> str:
    """Build user prompt for personal cheatsheet PDF generation (Step 5).

    Requests structured JSON output matching CheatsheetResponse.
    Only generates opening_statement and question_groups — the PDF builder
    renders concerns, frequency stats, scenarios, and what-to-bring sections.
    """
    # Sanitize user-generated content to prevent prompt injection
    sanitized_narrative = sanitize_prompt_input(narrative)
    sanitized_concerns = sanitize_prompt_input(concerns_text)
    sanitized_urgent = sanitize_prompt_input(urgent_symptom)
    sanitized_ask = sanitize_prompt_input(specific_ask)

    urgent_line = (
        f"- Urgent Concern: {sanitized_urgent}\n"
        if sanitized_urgent != "not provided"
        else ""
    )
    ask_line = (
        f"- Specific ask: {sanitized_ask}\n" if sanitized_ask != "not provided" else ""
    )

    return (
        f"Write a personal appointment preparation document for a patient.\n"
        f"This is her working document — concise, actionable, no fluff.\n\n"
        f"CRITICAL: Only use information provided below. Do NOT invent or assume content.\n"
        f"Do NOT suggest treatments or medications.\n\n"
        f"Patient Data:\n"
        f"- Age: {age_str}\n"
        f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
        f"- Primary Goal: {goal.replace('_', ' ')}\n"
        f"{urgent_line}"
        f"{ask_line}"
        f"- Prioritized Concerns: {sanitized_concerns}\n"
        f"- Narrative Summary: {sanitized_narrative}\n\n"
        f"Return ONLY a valid JSON object with exactly these fields:\n"
        f'{{"opening_statement": "2-3 sentences: age, perimenopause/menopause stage, '
        f'urgent concern if any, primary goal for today", '
        f'"question_groups": ['
        f'{{"topic": "topic name", "questions": ["open-ended question 1", "open-ended question 2"]}}'
        f"]}}\n\n"
        f"Rules for question_groups:\n"
        f"- Group 3-6 questions under 2-4 topic headings relevant to the patient's concerns\n"
        f"- Questions must be open-ended information-gathering, not treatment requests\n"
        f"- Start with 'Could you help me understand', 'What might explain', or similar\n"
        f"- No specific medication names. No diagnosis requests.\n\n"
        f"No markdown. No explanation. No extra fields. Valid JSON only."
    )
