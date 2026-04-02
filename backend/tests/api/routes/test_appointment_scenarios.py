"""Unit tests for appointment scenario selection.

Tests the _select_scenarios() helper after the JSON-config refactor.
_get_scenario_category() has been deleted — category comes from config/scenarios.json.

Note: this file lives in tests/api/routes/ for historical reasons but tests a
service-layer helper, not an HTTP route.
"""

from app.models.appointment import (
    AppointmentContext,
    AppointmentGoal,
    AppointmentType,
    DismissalExperience,
)
from app.services.appointment import AppointmentService

_svc = AppointmentService.__new__(AppointmentService)
_svc._scenario_config = _svc._load_scenario_config()
_select_scenarios = _svc._select_scenarios

VALID_CATEGORIES = {
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


def _ctx(goal, dismissed=DismissalExperience.no, urgent=None):
    return AppointmentContext(
        appointment_type=AppointmentType.new_provider,
        goal=goal,
        dismissed_before=dismissed,
        urgent_symptom=urgent,
    )


def _titles(scenarios: list) -> list[str]:
    return [s["title"] for s in scenarios]


class TestSelectScenarios:
    """Scenario selection returns list[dict] with title and category from config."""

    def test_explore_hrt_goal_scenarios(self):
        # CATCHES: explore_hrt goal key mismatch in JSON lookup — returns [] instead
        # of HRT-related scenarios
        scenarios = _select_scenarios(_ctx(AppointmentGoal.explore_hrt), "exploration")
        titles = _titles(scenarios)
        assert "Hormone therapy increases breast cancer risk" in titles
        assert "I don't prescribe that, I give the birth control pill instead" in titles
        assert "Let's try an antidepressant first" in titles
        assert len(scenarios) <= 7

    def test_optimize_current_treatment_scenarios(self):
        # CATCHES: optimize_current_treatment key not found — treatment-adjustment
        # dismissals would be missing for this common appointment goal
        scenarios = _select_scenarios(
            _ctx(AppointmentGoal.optimize_current_treatment), "active"
        )
        titles = _titles(scenarios)
        assert "Your symptoms aren't severe enough to treat" in titles
        assert "That dose is already too high" in titles
        assert "Let's try lifestyle changes first" in titles
        assert len(scenarios) <= 7

    def test_assess_status_goal_scenarios(self):
        # CATCHES: assess_status scenarios silently empty — common deflections
        # ("go away on their own") would be absent for initial-assessment appointments
        scenarios = _select_scenarios(
            _ctx(AppointmentGoal.assess_status), "preparation"
        )
        titles = _titles(scenarios)
        assert "Your symptoms will go away on their own" in titles
        assert "You're just stressed or anxious" in titles
        assert len(scenarios) <= 7

    def test_no_duplicate_titles(self):
        # CATCHES: dedup logic broken (e.g. comparing dicts by identity) —
        # universal scenarios that overlap with goal scenarios would appear twice
        scenarios = _select_scenarios(_ctx(AppointmentGoal.explore_hrt), "exploration")
        titles = _titles(scenarios)
        assert len(titles) == len(set(titles)), "Scenario titles contain duplicates"

    def test_max_seven_scenarios(self):
        # CATCHES: cap removed from [:7] slice — LLM prompt for scenario suggestions
        # could receive 10+ scenarios and exceed token budget
        for goal in [
            AppointmentGoal.explore_hrt,
            AppointmentGoal.optimize_current_treatment,
            AppointmentGoal.assess_status,
        ]:
            scenarios = _select_scenarios(_ctx(goal), "exploration")
            assert len(scenarios) <= 7, (
                f"Too many scenarios for {goal}: {len(scenarios)}"
            )

    def test_dismissed_before_does_not_add_trigger_question(self):
        # CATCHES: dismissed_before logic left in code — "What are the triggers?"
        # is not a dismissal scenario and was intentionally removed
        scenarios = _select_scenarios(
            _ctx(
                AppointmentGoal.explore_hrt,
                dismissed=DismissalExperience.multiple_times,
            ),
            "transition",
        )
        titles = _titles(scenarios)
        assert "What are the triggers?" not in titles

    def test_all_returned_scenarios_have_valid_categories(self):
        # CATCHES: a scenario added to JSON with an unknown category value —
        # frontend would silently render it without a style/group
        for goal in [
            AppointmentGoal.explore_hrt,
            AppointmentGoal.optimize_current_treatment,
            AppointmentGoal.assess_status,
        ]:
            scenarios = _select_scenarios(_ctx(goal), "exploration")
            for s in scenarios:
                assert s["category"] in VALID_CATEGORIES, (
                    f"Invalid category '{s['category']}' for scenario '{s['title']}'"
                )

    def test_all_returned_scenarios_are_dicts_with_required_keys(self):
        # CATCHES: JSON loaded but scenario format changed — missing "title" or
        # "category" key would crash generate_scenarios() with KeyError
        scenarios = _select_scenarios(_ctx(AppointmentGoal.explore_hrt), "exploration")
        for s in scenarios:
            assert isinstance(s, dict)
            assert "title" in s and isinstance(s["title"], str)
            assert "category" in s and isinstance(s["category"], str)
