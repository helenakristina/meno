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
     → generate_pdf_content("provider_summary") in llm.py (Step 5)

  6. CHEATSHEET / build_cheatsheet_user_prompt
     → generate_pdf_content("personal_cheatsheet") in llm.py (Step 5)
"""

from datetime import date


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
    "- Ground responses in current evidence and research (NAMS guidelines, peer-reviewed studies, major medical organizations)\n"
    "- Address the specific dismissal directly and acknowledge the provider's perspective\n"
    "- Provide concrete language she can use in the appointment\n"
    "- Reference specific research/statistics when relevant (e.g., 'Research shows...', 'The NAMS guidelines state...')\n"
    "- Never diagnose or prescribe, but DO reference evidence-based information\n"
    "- Empower her to advocate for herself\n"
    "- Acknowledge her experience and validate her concerns\n"
    "- Make responses conversational and natural (2-3 sentences max)\n"
    "- Return ONLY a valid JSON array with no markdown, no explanation\n"
    '- Each object must have: {"scenario_title": string, "suggestion": string}'
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
) -> str:
    """Build user prompt for clinical narrative generation (Step 2)."""
    return (
        f"Write a 2–3 paragraph clinical summary for a healthcare appointment. "
        f"Patient context: {appt_type_str} appointment, goal is '{goal_str}', "
        f"age {age_str}, journey stage: {journey_stage}. "
        f"Symptom tracking covers {days_back} days "
        f"({start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}).\n\n"
        f"Most frequently logged symptoms:\n{freq_text}\n\n"
        f"Symptom patterns (co-occurrences):\n{coocc_text}"
        f"{med_section}\n\n"
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
    context_section = f"\nAdditional context: {user_context}" if user_context else ""
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
) -> str:
    """Build user prompt for scenario suggestion generation (Step 4)."""
    return (
        f"A woman (age {age_str}) is preparing for a healthcare appointment. "
        f"She may encounter these dismissals specific to her situation:\n\n"
        f"{scenarios_text}\n\n"
        f"Her context:\n"
        f"- Appointment type: {appointment_type.replace('_', ' ')}\n"
        f"- What she's here to discuss: {goal.replace('_', ' ')}\n"
        f"- Prior dismissal experience: {dismissed_before.replace('_', ' ')}\n"
        f"- Her top concerns (in order):\n{concerns_text}\n\n"
        f"For EACH dismissal scenario above, generate a confident, evidence-based response "
        f"she can use IN THIS EXACT APPOINTMENT. Requirements:\n\n"
        f"1. Acknowledge the provider's concern (don't dismiss them)\n"
        f"2. Provide evidence-based reasoning (don't make up sources)\n"
        f"3. Redirect to actionable discussion\n"
        f"4. Keep to 2-3 sentences (realistic for appointment)\n"
        f"5. Use conversational 'I' language\n\n"
        f"CRITICAL: Do NOT include URLs or citations. We don't have verified sources to cite yet.\n"
        f"Focus on clear, confident, evidence-based language.\n\n"
        f"Return ONLY valid JSON with this exact structure, no markdown or explanation:\n"
        f'{{"scenarios": [{{"scenario_title": "...", "suggestion": "...", "sources": []}}]}}'
    )


def build_provider_summary_user_prompt(
    narrative: str,
    concerns_text: str,
    appointment_type: str,
    goal: str,
    age_str: str,
    urgent_symptom: str | None = None,
) -> str:
    """Build user prompt for provider summary PDF generation (Step 5)."""
    urgent_concern = urgent_symptom if urgent_symptom else "not provided"
    urgent_lead = f"Patient's urgent concern: {urgent_symptom}. " if urgent_symptom else ""
    return (
        f"Write a clinical summary for a healthcare provider seeing this patient.\n"
        f"This provider will read this in 2 minutes. Make it scannable and useful.\n\n"
        f"CRITICAL: Only describe what's in the data below. Do NOT invent symptoms, frequencies, or connections.\n"
        f"This is NOT a recommendation document—just describe the picture and let the provider decide.\n\n"
        f"Patient Data:\n"
        f"- Age: {age_str}\n"
        f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
        f"- Goal: {goal.replace('_', ' ')}\n"
        f"- Urgent Concern: {urgent_concern}\n"
        f"- Narrative Summary: {narrative}\n"
        f"- Concerns List: {concerns_text if concerns_text else 'None provided'}\n\n"
        f"{urgent_lead}\n\n"
        f"Structure:\n\n"
        f"1. OPENING (2-3 sentences) - Who, why, urgent concern\n"
        f"2. SYMPTOM PICTURE (3-4 sentences) - What she's experiencing (from narrative only)\n"
        f"3. KEY PATTERNS (2-3 sentences, ONLY if narrative mentions them)\n"
        f"4. PRIORITIZED CONCERNS (bulleted, exactly as provided)\n"
        f"5. CLOSING (1-2 sentences) - What patient is seeking\n\n"
        f"Tone: Conversational clinical. Specific numbers. No recommendations. No speculation.\n"
        f"Length: 1-2 pages maximum, scannable."
    )


def build_cheatsheet_user_prompt(
    narrative: str,
    concerns_text: str,
    appointment_type: str,
    goal: str,
    age_str: str,
    urgent_symptom: str | None = None,
    scenarios: list[dict] | None = None,
) -> str:
    """Build user prompt for personal cheatsheet PDF generation (Step 5)."""
    urgent_concern = urgent_symptom if urgent_symptom else "not provided"
    urgent_emphasis = (
        f"\nURGENT SYMPTOM: {urgent_symptom}\n"
        f"This is your primary concern for this appointment. Make sure it's the focus of your conversation."
        if urgent_symptom
        else ""
    )

    sideways_section = ""
    if scenarios:
        sideways_section = "5. 'IF THINGS GO SIDEWAYS'\n\n"
        for scenario in scenarios[:5]:
            title = scenario.get("title", "")
            suggestion = scenario.get("suggestion", "")
            sideways_section += f'- **If they say:** "{title}"\n  **You can say:** {suggestion}\n\n'

    return (
        f"Write a personal preparation document for a patient's healthcare appointment.\n"
        f"This is HER working document—concise, actionable, no fluff.\n\n"
        f"CRITICAL: Only use information provided below. Do NOT invent or assume content.\n"
        f"Do NOT suggest treatments or medications. Do NOT add context that wasn't provided.\n\n"
        f"Patient Data:\n"
        f"- Age: {age_str}\n"
        f"- Appointment Type: {appointment_type.replace('_', ' ')}\n"
        f"- Primary Goal: {goal.replace('_', ' ')}\n"
        f"- Urgent Concern: {urgent_concern}\n"
        f"- Prioritized Concerns: {concerns_text}\n"
        f"- Narrative Summary: {narrative}\n"
        f"{urgent_emphasis}\n\n"
        f"{sideways_section}"
        f"Structure:\n\n"
        f"1. OPENING STATEMENT (2-3 sentences) - Age, stage, urgent symptom, goal\n"
        f"2. SYMPTOMS RANKED BY IMPACT - urgent symptom first (if provided), then prioritized concerns\n"
        f"3. KEY CONCERNS (bulleted, from provided list only)\n"
        f"4. QUESTIONS TO ASK (grouped by topic, open-ended)\n"
        f"5. 'IF THINGS GO SIDEWAYS' - Use ONLY the dismissal scenarios provided above\n"
        f"6. WHAT TO BRING - symptom log, current medications, medical history, recent labs\n\n"
        f"CRITICAL RULES:\n"
        f"- Only reference symptoms/concerns that are in the data\n"
        f"- Do NOT suggest treatments\n"
        f"- Do NOT add emotional language or encouragement\n"
        f"- For 'If Things Go Sideways': Use EXACT dismissals and responses from above\n\n"
        f"Tone: Professional, concise, working document. No motivation speeches.\n"
        f"Length: 2-3 pages maximum."
    )
