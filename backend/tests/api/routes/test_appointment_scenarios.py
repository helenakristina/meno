"""Unit tests for appointment scenario selection and categorization.

Tests the _select_scenarios() and _get_scenario_category() helper functions
to ensure realistic dismissal scenarios are properly selected based on context
and correctly categorized.
"""

import sys
from pathlib import Path

# Add app to path for imports
app_path = Path(__file__).parent.parent.parent.parent / "app"
sys.path.insert(0, str(app_path.parent))

from app.services.appointment import AppointmentService

# Create a minimal service instance to access private helpers under test
_svc = AppointmentService.__new__(AppointmentService)
_select_scenarios = _svc._select_scenarios
_get_scenario_category = _svc._get_scenario_category
from app.models.appointment import (
    AppointmentContext,
    AppointmentType,
    AppointmentGoal,
    DismissalExperience,
)


class TestSelectScenarios:
    """Test scenario selection based on appointment context."""

    def test_explore_hrt_goal_scenarios(self):
        """For explore_hrt goal, select HRT-specific dismissals."""
        context = AppointmentContext(
            appointment_type=AppointmentType.new_provider,
            goal=AppointmentGoal.explore_hrt,
            dismissed_before=DismissalExperience.no,
        )
        scenarios = _select_scenarios(context, "exploration")

        # Should include HRT-specific dismissals
        assert "Hormone therapy increases breast cancer risk" in scenarios
        assert "I don't prescribe that, I give the birth control pill instead" in scenarios
        assert "Let's try an antidepressant first" in scenarios
        assert len(scenarios) <= 7

    def test_optimize_current_treatment_scenarios(self):
        """For optimize_current_treatment goal, select treatment adjustment dismissals."""
        context = AppointmentContext(
            appointment_type=AppointmentType.established_relationship,
            goal=AppointmentGoal.optimize_current_treatment,
            dismissed_before=DismissalExperience.no,
        )
        scenarios = _select_scenarios(context, "active")

        # Should include treatment adjustment dismissals
        assert "Your symptoms aren't severe enough to treat" in scenarios
        assert "That dose is already too high" in scenarios
        assert "Let's try lifestyle changes first" in scenarios
        assert len(scenarios) <= 7

    def test_assess_status_goal_scenarios(self):
        """For assess_status goal, select dismissal and deflection scenarios."""
        context = AppointmentContext(
            appointment_type=AppointmentType.new_provider,
            goal=AppointmentGoal.assess_status,
            dismissed_before=DismissalExperience.no,
        )
        scenarios = _select_scenarios(context, "preparation")

        # Should include time-based and psychology dismissals
        assert "Your symptoms will go away on their own" in scenarios
        assert "You're just stressed or anxious" in scenarios
        assert len(scenarios) <= 7

    def test_multiple_dismissals_adds_context_scenarios(self):
        """Users dismissed multiple times get additional deflection scenarios."""
        context = AppointmentContext(
            appointment_type=AppointmentType.new_provider,
            goal=AppointmentGoal.explore_hrt,
            dismissed_before=DismissalExperience.multiple_times,
        )
        scenarios = _select_scenarios(context, "transition")

        # Should include HRT scenarios + dismissal experience scenarios
        assert "Hormone therapy increases breast cancer risk" in scenarios
        assert "What are the triggers?" in scenarios
        assert len(scenarios) <= 7

    def test_once_or_twice_dismissal_adds_trigger_question(self):
        """Users dismissed 1-2 times get trigger question scenario."""
        context = AppointmentContext(
            appointment_type=AppointmentType.new_provider,
            goal=AppointmentGoal.explore_hrt,
            dismissed_before=DismissalExperience.once_or_twice,
        )
        scenarios = _select_scenarios(context, "preparation")

        # Should include HRT scenarios + trigger question
        assert "Hormone therapy increases breast cancer risk" in scenarios
        assert "What are the triggers?" in scenarios
        assert len(scenarios) <= 7

    def test_no_duplicate_scenarios(self):
        """Scenario list is deduplicated when same scenario selected multiple times."""
        # This scenario selection shouldn't have duplicates, but dedup is a safeguard
        context = AppointmentContext(
            appointment_type=AppointmentType.new_provider,
            goal=AppointmentGoal.explore_hrt,
            dismissed_before=DismissalExperience.multiple_times,
        )
        scenarios = _select_scenarios(context, "exploration")

        # Check for duplicates
        assert len(scenarios) == len(set(scenarios)), "Scenarios contain duplicates"

    def test_max_seven_scenarios(self):
        """Scenario list never exceeds 7 items."""
        for goal in [
            AppointmentGoal.explore_hrt,
            AppointmentGoal.optimize_current_treatment,
            AppointmentGoal.assess_status,
        ]:
            for dismissed in [
                DismissalExperience.no,
                DismissalExperience.once_or_twice,
                DismissalExperience.multiple_times,
            ]:
                context = AppointmentContext(
                    appointment_type=AppointmentType.new_provider,
                    goal=goal,
                    dismissed_before=dismissed,
                )
                scenarios = _select_scenarios(context, "exploration")
                assert len(scenarios) <= 7, f"Too many scenarios for {goal}: {len(scenarios)}"

    def test_all_scenarios_are_realistic_dismissals(self):
        """All returned scenarios are real dismissals users experience."""
        valid_scenarios = {
            "Hormone therapy increases breast cancer risk",
            "I don't prescribe that, I give the birth control pill instead",
            "Let's try an antidepressant first",
            "Your symptoms aren't severe enough to treat",
            "That dose is already too high",
            "Let's try lifestyle changes first",
            "Your symptoms will go away on their own",
            "You're just stressed or anxious",
            "You're too old to start hormone therapy",
            "What are the triggers?",
        }

        for goal in [
            AppointmentGoal.explore_hrt,
            AppointmentGoal.optimize_current_treatment,
            AppointmentGoal.assess_status,
        ]:
            for dismissed in [
                DismissalExperience.no,
                DismissalExperience.once_or_twice,
                DismissalExperience.multiple_times,
            ]:
                context = AppointmentContext(
                    appointment_type=AppointmentType.new_provider,
                    goal=goal,
                    dismissed_before=dismissed,
                )
                scenarios = _select_scenarios(context, "exploration")
                for scenario in scenarios:
                    assert scenario in valid_scenarios, f"Invalid scenario: {scenario}"


class TestGetScenarioCategory:
    """Test scenario categorization."""

    def test_hrt_concerns_category(self):
        """Scenarios about HRT risks are categorized as hrt-safety."""
        assert (
            _get_scenario_category("Hormone therapy increases breast cancer risk")
            == "hrt-safety"
        )

    def test_alternative_treatment_category(self):
        """Scenarios offering alternative treatments are categorized correctly."""
        assert (
            _get_scenario_category("I don't prescribe that, I give the birth control pill instead")
            == "general"  # Doesn't match specific patterns in new categorization
        )

    def test_dismissal_psychology_category(self):
        """Scenarios blaming psychology are categorized as wrong-specialist or psychology."""
        assert _get_scenario_category("Let's try an antidepressant first") == "wrong-specialist"
        assert _get_scenario_category("You're just stressed or anxious") == "psychology"

    def test_treatment_adjustment_category(self):
        """Scenarios about dose/severity are categorized as dismissal."""
        assert _get_scenario_category("Your symptoms aren't severe enough to treat") == "dismissal"
        assert _get_scenario_category("That dose is already too high") == "dismissal"

    def test_deflection_category(self):
        """Scenarios deflecting with questions/lifestyle are categorized by type."""
        assert _get_scenario_category("What are the triggers?") == "general"
        assert _get_scenario_category("Let's try lifestyle changes first") == "lifestyle-only"

    def test_dismissal_category(self):
        """Scenarios about waiting it out are categorized as wait-and-see."""
        assert _get_scenario_category("Your symptoms will go away on their own") == "wait-and-see"

    def test_category_case_insensitive(self):
        """Category detection is case-insensitive."""
        assert _get_scenario_category("HORMONE THERAPY INCREASES BREAST CANCER RISK") == "hrt-safety"
        assert _get_scenario_category("YOU'RE JUST STRESSED") == "psychology"

    def test_unknown_scenario_defaults_to_general(self):
        """Unknown scenarios default to 'general' category."""
        assert _get_scenario_category("Some random provider comment") == "general"

    def test_all_selected_scenarios_have_valid_categories(self):
        """All scenarios selected in context have valid categories."""
        valid_categories = {
            "hrt-safety",
            "wrong-specialist",
            "normalization",
            "specialist-referral",
            "dismissal",
            "lifestyle-only",
            "wait-and-see",
            "psychology",
            "general",
        }

        for goal in [
            AppointmentGoal.explore_hrt,
            AppointmentGoal.optimize_current_treatment,
            AppointmentGoal.assess_status,
        ]:
            for dismissed in [
                DismissalExperience.no,
                DismissalExperience.once_or_twice,
                DismissalExperience.multiple_times,
            ]:
                context = AppointmentContext(
                    appointment_type=AppointmentType.new_provider,
                    goal=goal,
                    dismissed_before=dismissed,
                )
                scenarios = _select_scenarios(context, "exploration")
                for scenario in scenarios:
                    category = _get_scenario_category(scenario)
                    assert (
                        category in valid_categories
                    ), f"Invalid category '{category}' for scenario '{scenario}'"
