"""Shared utilities for formatting symptom stats into LLM prompt text.

Pure functions with no side effects, no DB access, and no HTTP context.
Used by appointment.py and llm.py to avoid duplicating formatting logic.
"""

from app.models.medications import MedicationResponse
from app.models.symptoms import SymptomFrequency, SymptomPair


def format_frequency_stats_for_prompt(
    frequency_stats: list[SymptomFrequency],
    max_items: int = 10,
    include_category: bool = True,
    empty_msg: str = "No symptom data available.",
) -> str:
    """Format symptom frequency stats as prompt-ready text.

    Args:
        frequency_stats: Symptom occurrence counts to format.
        max_items: Maximum number of symptoms to include.
        include_category: If True (default), includes the symptom category in
            parentheses. Set False for provider-questions prompts which omit it.
        empty_msg: Sentinel string returned when frequency_stats is empty.

    Returns:
        Formatted string, one symptom per line, or empty_msg if no stats.
    """
    if not frequency_stats:
        return empty_msg
    if include_category:
        lines = [
            f"- {s.symptom_name} ({s.category}): logged {s.count} time(s)"
            for s in frequency_stats[:max_items]
        ]
    else:
        lines = [
            f"- {s.symptom_name}: logged {s.count} time(s)"
            for s in frequency_stats[:max_items]
        ]
    return "\n".join(lines)


def format_cooccurrence_stats_for_prompt(
    cooccurrence_stats: list[SymptomPair],
    max_items: int = 5,
    verbose: bool = True,
) -> str:
    """Format symptom co-occurrence stats as prompt-ready text.

    Args:
        cooccurrence_stats: Symptom pairs sorted by co-occurrence rate.
        max_items: Maximum number of pairs to include.
        verbose: If True (default), includes the co-occurrence rate as a
            percentage. Set False for provider-questions prompts which use the
            compact "X and Y co-occurred N time(s)" format without the rate.

    Returns:
        Formatted string, one pair per line, or sentinel if no stats.
    """
    if not cooccurrence_stats:
        return "No notable co-occurrence patterns."
    if verbose:
        lines = [
            f"- {p.symptom1_name} + {p.symptom2_name}: "
            f"co-occurred {p.cooccurrence_count} time(s) "
            f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
            for p in cooccurrence_stats[:max_items]
        ]
    else:
        lines = [
            f"- {p.symptom1_name} and {p.symptom2_name} "
            f"co-occurred {p.cooccurrence_count} time(s)"
            for p in cooccurrence_stats[:max_items]
        ]
    return "\n".join(lines)


def format_medications_for_prompt(medications: list[MedicationResponse]) -> str:
    """Format current medications as prompt-ready text.

    Args:
        medications: List of medication objects with medication_name, dose,
            delivery_method, and optional start_date attributes.

    Returns:
        Formatted medication section string with a leading double newline, or
        an empty string if medications is empty.
    """
    if not medications:
        return ""
    lines = [
        f"- {m.medication_name} {m.dose} ({m.delivery_method})"
        + (f", started {m.start_date}" if m.start_date else "")
        for m in medications
    ]
    return "\n\nCurrent MHT medications:\n" + "\n".join(lines)
