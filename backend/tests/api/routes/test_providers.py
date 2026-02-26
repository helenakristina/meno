"""Tests for provider directory endpoints.

All Supabase calls are mocked via FastAPI's dependency_overrides.
Provider endpoints are public — no auth required.
Calling script endpoint requires auth — mocked via dependency_overrides.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user_id
from app.core.supabase import get_client
from app.main import app


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockQueryBuilder:
    """Fluent builder mock supporting arbitrary method chaining + async execute()."""

    def __init__(self, data=None):
        self._data = data if data is not None else []

    def select(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    def in_(self, *_, **__):
        return self

    def limit(self, *_, **__):
        return self

    def range(self, *_, **__):
        return self

    def order(self, *_, **__):
        return self

    def insert(self, *_, **__):
        return self

    def update(self, *_, **__):
        return self

    def delete(self, *_, **__):
        return self

    async def execute(self):
        result = MagicMock()
        result.data = self._data
        return result


def make_mock_client(data=None) -> MagicMock:
    """Build a mock client that returns the same data for every table query."""
    mock = MagicMock()
    mock.table.side_effect = lambda _: MockQueryBuilder(data=data or [])
    return mock


def make_zip_mock_client(zip_data: list[dict], provider_data: list[dict]) -> MagicMock:
    """Build a mock client whose first table() call returns zip_data and subsequent
    calls return provider_data. Used for testing zip_code lookup + main query."""
    mock = MagicMock()
    call_count = [0]

    def table_side_effect(_):
        call_count[0] += 1
        if call_count[0] == 1:
            return MockQueryBuilder(data=zip_data)
        return MockQueryBuilder(data=provider_data)

    mock.table.side_effect = table_side_effect
    return mock


def make_sequential_client(*responses: list[dict]) -> MagicMock:
    """Build a mock client where successive table() calls return successive responses.

    Used for endpoints that make multiple DB queries (e.g., check-then-insert,
    or fetch-shortlist-entries then fetch-provider-rows).
    """
    mock = MagicMock()
    call_idx = [0]

    def table_side_effect(_):
        idx = call_idx[0]
        data = responses[idx] if idx < len(responses) else []
        call_idx[0] += 1
        return MockQueryBuilder(data=data)

    mock.table.side_effect = table_side_effect
    return mock


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


def override_both(mock_client):
    """Override both the DB client and auth dependency. Returns cleanup fn."""
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-uuid"
    return lambda: app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample provider fixtures
# ---------------------------------------------------------------------------

PROVIDER_MN = {
    "id": "uuid-1",
    "name": "Dr. Jane Smith",
    "credentials": "MD",
    "practice_name": "Women's Health Clinic",
    "city": "Minneapolis",
    "state": "MN",
    "zip_code": "55401",
    "phone": "612-555-0100",
    "website": "https://example.com",
    "nams_certified": True,
    "provider_type": "ob_gyn",
    "specialties": ["menopause", "perimenopause"],
    "insurance_accepted": ["Aetna", "Blue Cross"],
    "data_source": "nams_directory",
    "last_verified": "2026-01-15",
}

PROVIDER_MN_2 = {
    **PROVIDER_MN,
    "id": "uuid-2",
    "name": "Dr. Alice Johnson",
    "city": "Rochester",
    "insurance_accepted": ["Cigna", "United"],
}


# ---------------------------------------------------------------------------
# GET /api/providers/search
# ---------------------------------------------------------------------------


class TestSearchProviders:
    def test_returns_paginated_results_for_state(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert body["total_pages"] == 1
        assert len(body["providers"]) == 2
        # Spot-check one provider card shape
        p = body["providers"][0]
        assert "id" in p and "name" in p and "city" in p and "state" in p
        assert isinstance(p["specialties"], list)
        assert isinstance(p["insurance_accepted"], list)

    def test_returns_400_when_no_state_or_zip(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search")
        finally:
            cleanup()

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "state" in detail or "zip" in detail

    def test_returns_422_when_page_size_exceeds_50(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN&page_size=51")
        finally:
            cleanup()

        assert response.status_code == 422

    def test_city_exact_match_filters_results(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN&city=Minneapolis")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["providers"][0]["city"] == "Minneapolis"

    def test_city_case_insensitive_exact_match(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN&city=minneapolis")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_city_partial_match_fallback_when_no_exact_match(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                # "chester" is a substring of "Rochester" but not an exact match
                response = client.get("/api/providers/search?state=MN&city=chester")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["providers"][0]["city"] == "Rochester"

    def test_city_no_results_when_no_match(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN&city=Duluth")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_insurance_filter_case_insensitive(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                # "aetna" should match PROVIDER_MN which has "Aetna"
                response = client.get("/api/providers/search?state=MN&insurance=aetna")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["providers"][0]["id"] == "uuid-1"

    def test_insurance_filter_no_match_returns_empty(self):
        mock = make_mock_client(data=[PROVIDER_MN, PROVIDER_MN_2])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/providers/search?state=MN&insurance=NonExistentInsurance"
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_state_code_normalized_to_uppercase(self):
        """Lowercase state code should produce the same results as uppercase."""
        mock = make_mock_client(data=[PROVIDER_MN])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=mn")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_pagination_page_2_returns_correct_slice(self):
        providers = [
            {**PROVIDER_MN, "id": f"uuid-{i}", "name": f"Dr. Provider {i:02d}"}
            for i in range(3)
        ]
        mock = make_mock_client(data=providers)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/providers/search?state=MN&page=2&page_size=2"
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == 2
        assert body["total_pages"] == 2
        assert len(body["providers"]) == 1

    def test_nams_certified_providers_sorted_first(self):
        non_nams = {**PROVIDER_MN, "id": "uuid-non", "name": "Dr. AAA NonNams", "nams_certified": False}
        nams = {**PROVIDER_MN, "id": "uuid-nams", "name": "Dr. ZZZ Nams", "nams_certified": True}
        mock = make_mock_client(data=[non_nams, nams])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN&nams_only=false")
        finally:
            cleanup()

        assert response.status_code == 200
        providers = response.json()["providers"]
        # NAMS certified should appear before non-NAMS regardless of name order
        assert providers[0]["nams_certified"] is True
        assert providers[1]["nams_certified"] is False

    def test_zip_code_infers_state(self):
        """When zip_code is provided without state, state is looked up from providers."""
        mock = make_zip_mock_client(
            zip_data=[{"state": "MN"}],
            provider_data=[PROVIDER_MN],
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?zip_code=55401")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_zip_code_not_found_returns_400(self):
        mock = make_zip_mock_client(zip_data=[], provider_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?zip_code=99999")
        finally:
            cleanup()

        assert response.status_code == 400
        assert "zip_code" in response.json()["detail"]

    def test_empty_results_returns_valid_response_shape(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=WY")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["providers"] == []
        assert body["total_pages"] == 1

    def test_search_results_normalize_commercial_insurance(self):
        provider = {**PROVIDER_MN, "insurance_accepted": ["Commercial Insurance", "Medicare"]}
        mock = make_mock_client(data=[provider])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/search?state=MN")
        finally:
            cleanup()

        assert response.status_code == 200
        result_insurance = response.json()["providers"][0]["insurance_accepted"]
        assert "Private Insurance" in result_insurance
        assert "Commercial Insurance" not in result_insurance


# ---------------------------------------------------------------------------
# GET /api/providers/states
# ---------------------------------------------------------------------------


class TestListStates:
    def test_returns_states_with_counts_sorted_alphabetically(self):
        data = [
            {"state": "MN"},
            {"state": "MN"},
            {"state": "CA"},
            {"state": "TX"},
        ]
        mock = make_mock_client(data=data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/states")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        states = [item["state"] for item in body]
        assert states == sorted(states), "States should be alphabetically sorted"
        counts = {item["state"]: item["count"] for item in body}
        assert counts["CA"] == 1
        assert counts["MN"] == 2
        assert counts["TX"] == 1

    def test_returns_empty_list_when_no_providers(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/states")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json() == []

    def test_response_shape_has_state_and_count_fields(self):
        mock = make_mock_client(data=[{"state": "MN"}])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/states")
        finally:
            cleanup()

        assert response.status_code == 200
        item = response.json()[0]
        assert "state" in item
        assert "count" in item


# ---------------------------------------------------------------------------
# GET /api/providers/insurance-options
# ---------------------------------------------------------------------------


class TestListInsuranceOptions:
    def test_returns_sorted_deduplicated_options(self):
        data = [
            {"insurance_accepted": ["Cigna", "Aetna"]},
            {"insurance_accepted": ["Aetna", "Blue Cross"]},  # Aetna is a duplicate
        ]
        mock = make_mock_client(data=data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body == sorted({"Cigna", "Aetna", "Blue Cross"})
        assert len(body) == 3

    def test_returns_empty_list_when_no_insurance_data(self):
        mock = make_mock_client(data=[{"insurance_accepted": None}])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_empty_list_when_no_providers(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json() == []

    def test_alphabetical_ordering(self):
        data = [
            {"insurance_accepted": ["Zetra Health", "Aetna", "Medicare"]},
        ]
        mock = make_mock_client(data=data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        body = response.json()
        assert body == sorted(body)

    def test_commercial_insurance_normalized_to_private_insurance(self):
        data = [{"insurance_accepted": ["Commercial Insurance", "Medicare"]}]
        mock = make_mock_client(data=data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        body = response.json()
        assert "Private Insurance" in body
        assert "Commercial Insurance" not in body

    def test_deduplicates_after_normalization(self):
        """Both raw and canonical forms in the DB collapse to one entry."""
        data = [
            {"insurance_accepted": ["Commercial Insurance"]},
            {"insurance_accepted": ["Private Insurance"]},  # canonical already present
        ]
        mock = make_mock_client(data=data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/insurance-options")
        finally:
            cleanup()

        body = response.json()
        assert body.count("Private Insurance") == 1
        assert "Commercial Insurance" not in body


# ---------------------------------------------------------------------------
# POST /api/providers/calling-script
# ---------------------------------------------------------------------------

_MOCK_SCRIPT = "Hi, I'm calling to inquire about a new patient appointment with Dr. Smith."

_BASE_PAYLOAD = {
    "provider_id": "uuid-1",
    "provider_name": "Dr. Jane Smith",
    "insurance_type": "private",
    "insurance_plan_name": "Aetna PPO",
    "insurance_plan_unknown": False,
    "interested_in_telehealth": False,
}


def override_auth():
    """Override auth dependency to return a test user ID. Returns cleanup fn."""
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-uuid"
    return lambda: app.dependency_overrides.clear()


class TestGenerateCallingScript:
    def _post(self, client, payload):
        return client.post("/api/providers/calling-script", json=payload)

    def test_private_insurance_with_plan_returns_script(self):
        cleanup = override_auth()
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, _BASE_PAYLOAD)
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["provider_name"] == "Dr. Jane Smith"
        assert body["script"] == _MOCK_SCRIPT

    def test_private_insurance_no_plan_returns_script(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_plan_name": None}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_medicaid_with_plan_returns_script(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_type": "medicaid", "insurance_plan_name": "UCare"}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_medicaid_plan_unknown_returns_script(self):
        cleanup = override_auth()
        payload = {
            **_BASE_PAYLOAD,
            "insurance_type": "medicaid",
            "insurance_plan_name": None,
            "insurance_plan_unknown": True,
        }
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_medicare_with_advantage_plan_returns_script(self):
        cleanup = override_auth()
        payload = {
            **_BASE_PAYLOAD,
            "insurance_type": "medicare",
            "insurance_plan_name": "Humana Gold",
        }
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_medicare_original_no_plan_returns_script(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_type": "medicare", "insurance_plan_name": None}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_self_pay_returns_script(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_type": "self_pay", "insurance_plan_name": None}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_other_insurance_returns_script(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_type": "other"}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_telehealth_flag_accepted(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "interested_in_telehealth": True}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 200

    def test_blank_provider_name_returns_400(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "provider_name": "   "}
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(return_value=_MOCK_SCRIPT),
            ):
                with TestClient(app) as client:
                    response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 400
        assert "provider_name" in response.json()["detail"]

    def test_invalid_insurance_type_returns_422(self):
        cleanup = override_auth()
        payload = {**_BASE_PAYLOAD, "insurance_type": "not_valid"}
        try:
            with TestClient(app) as client:
                response = self._post(client, payload)
        finally:
            cleanup()

        assert response.status_code == 422

    def test_llm_failure_returns_500(self):
        cleanup = override_auth()
        try:
            with patch(
                "app.api.routes.providers.generate_calling_script",
                new=AsyncMock(side_effect=RuntimeError("OpenAI down")),
            ):
                with TestClient(app) as client:
                    response = self._post(client, _BASE_PAYLOAD)
        finally:
            cleanup()

        assert response.status_code == 500
        assert "calling script" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Shortlist / Call Tracker endpoints
# ---------------------------------------------------------------------------

# Sample shortlist fixture data
_SHORTLIST_ENTRY = {
    "id": "entry-uuid-1",
    "user_id": "test-user-uuid",
    "provider_id": "uuid-1",
    "status": "to_call",
    "notes": None,
    "added_at": "2026-02-25T10:00:00+00:00",
    "updated_at": "2026-02-25T10:00:00+00:00",
}

_SHORTLIST_ENTRY_WITH_NOTES = {
    **_SHORTLIST_ENTRY,
    "id": "entry-uuid-2",
    "provider_id": "uuid-2",
    "status": "left_voicemail",
    "notes": "Said to call back in March",
}


class TestGetShortlistIds:
    def test_returns_list_of_provider_ids(self):
        data = [{"provider_id": "uuid-1"}, {"provider_id": "uuid-2"}]
        mock = make_mock_client(data=data)
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist/ids")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body == ["uuid-1", "uuid-2"]

    def test_returns_empty_list_when_no_entries(self):
        mock = make_mock_client(data=[])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist/ids")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json() == []

    def test_requires_auth(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)  # DB override only — no auth override
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist/ids")
        finally:
            cleanup()

        assert response.status_code == 401


class TestGetShortlist:
    def test_returns_entries_with_provider_data(self):
        # Sequence: shortlist entries → provider rows
        mock = make_sequential_client(
            [_SHORTLIST_ENTRY],
            [PROVIDER_MN],
        )
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist")
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        entry = body[0]
        assert entry["provider_id"] == "uuid-1"
        assert entry["status"] == "to_call"
        assert "provider" in entry
        assert entry["provider"]["name"] == "Dr. Jane Smith"
        assert entry["provider"]["city"] == "Minneapolis"

    def test_returns_empty_list_when_shortlist_is_empty(self):
        mock = make_mock_client(data=[])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist")
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json() == []

    def test_entry_with_notes_is_included(self):
        mock = make_sequential_client(
            [_SHORTLIST_ENTRY_WITH_NOTES],
            [{**PROVIDER_MN, "id": "uuid-2"}],
        )
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist")
        finally:
            cleanup()

        assert response.status_code == 200
        entry = response.json()[0]
        assert entry["notes"] == "Said to call back in March"
        assert entry["status"] == "left_voicemail"

    def test_requires_auth(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/providers/shortlist")
        finally:
            cleanup()

        assert response.status_code == 401


class TestAddToShortlist:
    def test_adds_entry_and_returns_201(self):
        # Sequence: check existing (empty) → insert result
        new_entry = {**_SHORTLIST_ENTRY, "status": "to_call"}
        mock = make_sequential_client([], [new_entry])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/providers/shortlist", json={"provider_id": "uuid-1"}
                )
        finally:
            cleanup()

        assert response.status_code == 201
        body = response.json()
        assert body["provider_id"] == "uuid-1"
        assert body["status"] == "to_call"

    def test_returns_409_when_already_in_shortlist(self):
        # Sequence: check existing → found → returns 409 with existing entry
        mock = make_mock_client(data=[_SHORTLIST_ENTRY])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/providers/shortlist", json={"provider_id": "uuid-1"}
                )
        finally:
            cleanup()

        assert response.status_code == 409
        body = response.json()
        # The existing entry is returned in the body
        assert body["provider_id"] == "uuid-1"

    def test_requires_auth(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/providers/shortlist", json={"provider_id": "uuid-1"}
                )
        finally:
            cleanup()

        assert response.status_code == 401


class TestRemoveFromShortlist:
    def test_removes_entry_and_returns_204(self):
        # Sequence: check existing (found) → delete
        mock = make_sequential_client([_SHORTLIST_ENTRY], [])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.delete("/api/providers/shortlist/uuid-1")
        finally:
            cleanup()

        assert response.status_code == 204

    def test_returns_404_when_not_in_shortlist(self):
        mock = make_mock_client(data=[])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.delete("/api/providers/shortlist/uuid-99")
        finally:
            cleanup()

        assert response.status_code == 404
        assert "shortlist" in response.json()["detail"].lower()

    def test_requires_auth(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.delete("/api/providers/shortlist/uuid-1")
        finally:
            cleanup()

        assert response.status_code == 401


class TestUpdateShortlistEntry:
    def test_updates_status_returns_entry(self):
        updated_entry = {**_SHORTLIST_ENTRY, "status": "called"}
        # Sequence: check existing (found) → update result
        mock = make_sequential_client([_SHORTLIST_ENTRY], [updated_entry])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-1", json={"status": "called"}
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "called"

    def test_updates_notes_returns_entry(self):
        updated_entry = {**_SHORTLIST_ENTRY, "notes": "Call back in March"}
        mock = make_sequential_client([_SHORTLIST_ENTRY], [updated_entry])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-1",
                    json={"notes": "Call back in March"},
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["notes"] == "Call back in March"

    def test_updates_both_status_and_notes(self):
        updated_entry = {**_SHORTLIST_ENTRY, "status": "booking", "notes": "Appointment next week"}
        mock = make_sequential_client([_SHORTLIST_ENTRY], [updated_entry])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-1",
                    json={"status": "booking", "notes": "Appointment next week"},
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "booking"
        assert body["notes"] == "Appointment next week"

    def test_returns_404_when_not_in_shortlist(self):
        mock = make_mock_client(data=[])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-99", json={"status": "called"}
                )
        finally:
            cleanup()

        assert response.status_code == 404

    def test_invalid_status_returns_422(self):
        mock = make_mock_client(data=[])
        cleanup = override_both(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-1", json={"status": "not_a_status"}
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_requires_auth(self):
        mock = make_mock_client(data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.patch(
                    "/api/providers/shortlist/uuid-1", json={"status": "called"}
                )
        finally:
            cleanup()

        assert response.status_code == 401
