"""Unit tests for app.services.stats — pure calculation functions.

No DB or network access; all inputs are constructed inline.
"""

from app.services.stats import calculate_cooccurrence_stats, calculate_frequency_stats

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

REF = {
    "id-a": {"id": "id-a", "name": "Hot flashes", "category": "vasomotor"},
    "id-b": {"id": "id-b", "name": "Fatigue", "category": "energy"},
    "id-c": {"id": "id-c", "name": "Brain fog", "category": "cognitive"},
}

LOG_AB = {"symptoms": ["id-a", "id-b"]}
LOG_AC = {"symptoms": ["id-a", "id-c"]}
LOG_A = {"symptoms": ["id-a"]}
LOG_EMPTY = {"symptoms": []}
LOG_NONE = {"symptoms": None}


# ---------------------------------------------------------------------------
# calculate_frequency_stats
# ---------------------------------------------------------------------------


class TestCalculateFrequencyStats:
    def test_counts_are_sorted_descending(self):
        logs = [LOG_AB, LOG_AB, LOG_A]  # id-a: 3, id-b: 2
        stats = calculate_frequency_stats(logs, REF)
        assert stats[0].symptom_id == "id-a"
        assert stats[0].count == 3
        assert stats[1].symptom_id == "id-b"
        assert stats[1].count == 2

    def test_resolves_name_and_category(self):
        stats = calculate_frequency_stats([LOG_A], REF)
        assert len(stats) == 1
        assert stats[0].symptom_name == "Hot flashes"
        assert stats[0].category == "vasomotor"

    def test_empty_logs_returns_empty_list(self):
        assert calculate_frequency_stats([], REF) == []

    def test_logs_with_no_symptoms_returns_empty_list(self):
        assert calculate_frequency_stats([LOG_EMPTY, LOG_NONE], REF) == []

    def test_missing_ref_id_is_omitted(self):
        logs = [{"symptoms": ["id-a", "unknown-id"]}]
        stats = calculate_frequency_stats(logs, REF)
        ids = {s.symptom_id for s in stats}
        assert "id-a" in ids
        assert "unknown-id" not in ids

    def test_returns_symptom_frequency_objects(self):
        from app.models.symptoms import SymptomFrequency

        stats = calculate_frequency_stats([LOG_AB], REF)
        assert all(isinstance(s, SymptomFrequency) for s in stats)


# ---------------------------------------------------------------------------
# calculate_cooccurrence_stats
# ---------------------------------------------------------------------------


class TestCalculateCooccurrenceStats:
    def test_pair_detected_above_threshold(self):
        logs = [LOG_AB, LOG_AB]  # (a,b) co-occur 2×
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=2)
        assert len(pairs) == 1
        assert pairs[0].symptom1_id == "id-a"
        assert pairs[0].symptom2_id == "id-b"
        assert pairs[0].cooccurrence_count == 2

    def test_pair_below_threshold_excluded(self):
        logs = [LOG_AB]  # (a,b) co-occur 1× — below default threshold of 2
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=2)
        assert pairs == []

    def test_min_threshold_one_includes_single_cooccurrence(self):
        pairs = calculate_cooccurrence_stats([LOG_AB], REF, min_threshold=1)
        assert len(pairs) == 1

    def test_cooccurrence_rate_calculation(self):
        # id-a appears in 3 logs; co-occurs with id-b in 2 → rate = 2/3
        logs = [LOG_AB, LOG_AB, LOG_AC]
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=2)
        ab = next(
            p
            for p in pairs
            if {p.symptom1_id, p.symptom2_id} == {"id-a", "id-b"}
        )
        assert ab.cooccurrence_rate == round(2 / 3, 4)
        assert ab.total_occurrences_symptom1 == 3

    def test_sorted_by_rate_descending(self):
        # (a,b): a appears 2×, co-occurs 2× → rate 1.0
        # (a,c): a appears 2×, co-occurs 1× → rate 0.5
        logs = [LOG_AB, LOG_AB, LOG_AC]
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=1)
        rates = [p.cooccurrence_rate for p in pairs]
        assert rates == sorted(rates, reverse=True)

    def test_single_symptom_logs_ignored(self):
        # Only single-symptom logs — no pairs possible
        logs = [LOG_A, LOG_A, LOG_A]
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=1)
        assert pairs == []

    def test_empty_logs_returns_empty_list(self):
        assert calculate_cooccurrence_stats([], REF) == []

    def test_missing_ref_id_pair_is_skipped(self):
        logs = [{"symptoms": ["id-a", "unknown-id"]}, {"symptoms": ["id-a", "unknown-id"]}]
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=1)
        assert pairs == []

    def test_capped_at_max_pairs(self):
        from app.services.stats import MAX_COOCCURRENCE_PAIRS

        # Create more pairs than the cap by using many distinct symptom IDs
        many_ref = {f"id-{i}": {"name": f"Symptom {i}", "category": "other"} for i in range(20)}
        # Each log has all 20 symptoms → C(20,2)=190 unique pairs
        logs = [{"symptoms": list(many_ref.keys())}] * 3
        pairs = calculate_cooccurrence_stats(logs, many_ref, min_threshold=1)
        assert len(pairs) <= MAX_COOCCURRENCE_PAIRS

    def test_returns_symptom_pair_objects(self):
        from app.models.symptoms import SymptomPair

        logs = [LOG_AB, LOG_AB]
        pairs = calculate_cooccurrence_stats(logs, REF, min_threshold=2)
        assert all(isinstance(p, SymptomPair) for p in pairs)
