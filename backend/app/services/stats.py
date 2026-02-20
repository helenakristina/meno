"""Pure calculation functions for symptom statistics.

Stateless helpers that operate on pre-fetched data — no DB access. Callers
are responsible for fetching raw logs and the symptoms_reference lookup before
calling these functions.
"""
import itertools
import logging
from collections import Counter

from app.models.symptoms import SymptomFrequency, SymptomPair

logger = logging.getLogger(__name__)

# Maximum co-occurrence pairs returned — keeps responses manageable and
# dashboard cards readable.
MAX_COOCCURRENCE_PAIRS = 10


def calculate_frequency_stats(
    logs: list[dict],
    symptoms_reference: dict[str, dict],
) -> list[SymptomFrequency]:
    """Calculate per-symptom occurrence counts across a set of logs.

    Counts total occurrences, not unique days — a symptom appearing in 3
    separate logs contributes 3 to its count. Results are sorted by count
    descending.

    Symptom IDs not present in symptoms_reference are logged as warnings and
    omitted from the result (data-integrity anomalies, not caller errors).

    Args:
        logs: Raw symptom log rows from the database. Each row must have a
            ``symptoms`` field containing a list of symptom UUIDs.
        symptoms_reference: Mapping of symptom_id → ``{name, category}``
            from the symptoms_reference table.

    Returns:
        List of :class:`SymptomFrequency` objects sorted by count descending.
    """
    counts: Counter[str] = Counter(
        sid for row in logs for sid in (row.get("symptoms") or [])
    )

    stats: list[SymptomFrequency] = []
    for symptom_id, count in counts.most_common():
        ref = symptoms_reference.get(symptom_id)
        if ref:
            stats.append(
                SymptomFrequency(
                    symptom_id=symptom_id,
                    symptom_name=ref["name"],
                    category=ref["category"],
                    count=count,
                )
            )
        else:
            logger.warning(
                "Symptom ID %s not found in symptoms_reference (data integrity issue)",
                symptom_id,
            )

    return stats


def calculate_cooccurrence_stats(
    logs: list[dict],
    symptoms_reference: dict[str, dict],
    min_threshold: int = 2,
) -> list[SymptomPair]:
    """Calculate symptom pair co-occurrence rates above a minimum threshold.

    For each qualifying pair (A, B), the rate is computed from A's perspective:
    ``co_occurrences / total_logs_containing_A``. Pairs are ordered consistently
    by sorting the two IDs so (A, B) and (B, A) are never double-counted.

    Only logs with two or more distinct symptoms contribute to pair counts;
    single-symptom logs are ignored. Returns at most ``MAX_COOCCURRENCE_PAIRS``
    pairs (highest rate first).

    Pairs with symptom IDs missing from symptoms_reference are silently skipped
    (data-integrity anomalies logged as warnings).

    Args:
        logs: Raw symptom log rows from the database. Each row must have a
            ``symptoms`` field containing a list of symptom UUIDs.
        symptoms_reference: Mapping of symptom_id → ``{name, category}``
            from the symptoms_reference table.
        min_threshold: Minimum number of co-occurrences required to include a
            pair. Defaults to 2.

    Returns:
        List of :class:`SymptomPair` objects sorted by co-occurrence rate
        descending, capped at ``MAX_COOCCURRENCE_PAIRS``.
    """
    symptom_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()

    for row in logs:
        symptoms = list(dict.fromkeys(row.get("symptoms") or []))  # deduplicate, preserve order
        for sid in symptoms:
            symptom_counts[sid] += 1
        if len(symptoms) >= 2:
            for a, b in itertools.combinations(sorted(symptoms), 2):
                pair_counts[(a, b)] += 1

    pairs: list[SymptomPair] = []
    for (id_a, id_b), co_count in pair_counts.items():
        if co_count < min_threshold:
            continue
        ref_a = symptoms_reference.get(id_a)
        ref_b = symptoms_reference.get(id_b)
        if not ref_a or not ref_b:
            logger.warning(
                "Co-occurrence: symptom ID(s) missing from symptoms_reference "
                "(%s, %s) — skipping pair",
                id_a,
                id_b,
            )
            continue
        total_a = symptom_counts[id_a]
        rate = co_count / total_a if total_a else 0.0
        pairs.append(
            SymptomPair(
                symptom1_id=id_a,
                symptom1_name=ref_a["name"],
                symptom2_id=id_b,
                symptom2_name=ref_b["name"],
                cooccurrence_count=co_count,
                cooccurrence_rate=round(rate, 4),
                total_occurrences_symptom1=total_a,
            )
        )

    pairs.sort(key=lambda p: p.cooccurrence_rate, reverse=True)
    return pairs[:MAX_COOCCURRENCE_PAIRS]
