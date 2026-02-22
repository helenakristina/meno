"""Unit tests for the insurance name normalizer."""

from app.core.insurance_normalizer import normalize_insurance_list, normalize_insurance_name


class TestNormalizeInsuranceName:
    def test_known_mapping_returns_canonical_name(self):
        assert normalize_insurance_name("Commercial Insurance") == "Private Insurance"

    def test_unknown_value_returns_original(self):
        assert normalize_insurance_name("Tricare") == "Tricare"
        assert normalize_insurance_name("Aetna PPO") == "Aetna PPO"

    def test_empty_string_returns_empty_string(self):
        assert normalize_insurance_name("") == ""

    def test_near_miss_case_is_not_mapped(self):
        # Matching is case-sensitive — "commercial insurance" (lowercase) has no mapping
        assert normalize_insurance_name("commercial insurance") == "commercial insurance"
        assert normalize_insurance_name("COMMERCIAL INSURANCE") == "COMMERCIAL INSURANCE"

    def test_already_canonical_name_is_unchanged(self):
        assert normalize_insurance_name("Private Insurance") == "Private Insurance"


class TestNormalizeInsuranceList:
    def test_maps_known_values_in_list(self):
        result = normalize_insurance_list(["Commercial Insurance", "Medicare", "Medicaid"])
        assert result == ["Private Insurance", "Medicare", "Medicaid"]

    def test_unknown_values_pass_through_unchanged(self):
        result = normalize_insurance_list(["Tricare", "Aetna"])
        assert result == ["Tricare", "Aetna"]

    def test_empty_list_returns_empty_list(self):
        assert normalize_insurance_list([]) == []

    def test_mixed_list_normalizes_correctly(self):
        result = normalize_insurance_list(
            ["Commercial Insurance", "Tricare", "Commercial Insurance"]
        )
        assert result == ["Private Insurance", "Tricare", "Private Insurance"]

    def test_preserves_order(self):
        original = ["Tricare", "Commercial Insurance", "Medicare"]
        result = normalize_insurance_list(original)
        assert result == ["Tricare", "Private Insurance", "Medicare"]
