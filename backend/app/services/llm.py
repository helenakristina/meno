"""LLM service for generating symptom summaries and provider questions.

Uses OpenAI gpt-4o-mini for cost-effective generation during development.
All prompts use "logs show" language and never diagnose, prescribe, or recommend
specific treatments. See CLAUDE.md for the LLM provider migration strategy.
"""
import logging
from datetime import date

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.symptoms import SymptomFrequency, SymptomPair

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_symptom_summary(
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
        "Calling OpenAI for symptom summary: range=%s–%s symptoms=%d pairs=%d",
        start,
        end,
        len(frequency_stats),
        len(cooccurrence_stats),
    )

    response = await _client().chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=600,
        temperature=0.3,
    )

    summary = (response.choices[0].message.content or "").strip()
    logger.info("OpenAI summary generated: %d characters", len(summary))
    return summary


async def generate_provider_questions(
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
        "Calling OpenAI for provider questions: symptoms=%d pairs=%d",
        len(frequency_stats),
        len(cooccurrence_stats),
    )

    response = await _client().chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=500,
        temperature=0.4,
    )

    raw = (response.choices[0].message.content or "").strip()
    logger.info("OpenAI questions generated: %d characters", len(raw))

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
