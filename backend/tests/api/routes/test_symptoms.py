"""Tests for POST /api/symptoms/logs and GET /api/symptoms/logs.

All Supabase calls are mocked via FastAPI's dependency_overrides so no
real network connections are made.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.core.supabase import get_client
from app.main import app


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockQueryBuilder:
    """Fluent builder mock that supports arbitrary method chaining + async execute().

    Every builder method returns self so chains like
    .select("*").eq(...).order(...).limit(...) all resolve to one object.
    """

    def __init__(self, data=None, error=None):
        self._data = data if data is not None else []
        self._error = error

    def insert(self, *_, **__):
        return self

    def select(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    def in_(self, *_, **__):
        return self

    def gte(self, *_, **__):
        return self

    def lte(self, *_, **__):
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_, **__):
        return self

    async def execute(self):
        result = MagicMock()
        result.data = self._data
        result.error = self._error
        return result


def make_ref_data(symptom_ids: list[str]) -> list[dict]:
    """Build mock symptoms_reference rows matching the given IDs (all valid)."""
    return [
        {"id": sid, "name": f"Symptom {sid}", "category": "general"}
        for sid in set(symptom_ids)
    ]


def make_mock_client(
    user_id: str = "test-user-uuid",
    data=None,
    symptoms_ref_data=None,
    auth_error: Exception | None = None,
) -> MagicMock:
    mock = MagicMock()

    if auth_error:
        mock.auth.get_user = AsyncMock(side_effect=auth_error)
    else:
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id=user_id))
        )

    # Dispatch different builders per table so validation and insert
    # queries can return independent data.
    def table_side_effect(table_name):
        if table_name == "symptoms_reference":
            return MockQueryBuilder(data=symptoms_ref_data or [])
        return MockQueryBuilder(data=data or [])

    mock.table.side_effect = table_side_effect
    return mock


# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

STORED_LOG = {
    "id": "log-uuid-abc123",
    "user_id": USER_ID,
    "logged_at": datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    "symptoms": ["fatigue", "brain_fog"],
    "free_text_entry": None,
    "source": "cards",
}

CARDS_PAYLOAD = {
    "symptoms": ["fatigue", "brain_fog"],
    "source": "cards",
}

TEXT_PAYLOAD = {
    "symptoms": [],
    "source": "text",
    "free_text_entry": "Feeling very foggy and tired today",
}

BOTH_PAYLOAD = {
    "symptoms": ["fatigue"],
    "source": "both",
    "free_text_entry": "Worse than usual this morning",
}


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/symptoms/logs
# ---------------------------------------------------------------------------


class TestCreateSymptomLog:
    def test_returns_201_when_source_is_cards(self):
        mock = make_mock_client(
            user_id=USER_ID,
            data=[STORED_LOG],
            symptoms_ref_data=make_ref_data(CARDS_PAYLOAD["symptoms"]),
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == STORED_LOG["id"]
        assert body["user_id"] == USER_ID
        # symptoms are now enriched SymptomDetail objects, not raw ID strings
        assert [s["id"] for s in body["symptoms"]] == CARDS_PAYLOAD["symptoms"]
        assert all("name" in s and "category" in s for s in body["symptoms"])
        assert body["source"] == "cards"
        assert body["free_text_entry"] is None

    def test_returns_201_when_source_is_text(self):
        stored = {**STORED_LOG, "symptoms": [], "source": "text",
                  "free_text_entry": TEXT_PAYLOAD["free_text_entry"]}
        mock = make_mock_client(user_id=USER_ID, data=[stored])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=TEXT_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 201
        assert response.json()["source"] == "text"
        assert response.json()["free_text_entry"] == TEXT_PAYLOAD["free_text_entry"]

    def test_returns_201_when_source_is_both(self):
        stored = {**STORED_LOG, **BOTH_PAYLOAD}
        mock = make_mock_client(
            user_id=USER_ID,
            data=[stored],
            symptoms_ref_data=make_ref_data(BOTH_PAYLOAD["symptoms"]),
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=BOTH_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 201
        assert response.json()["source"] == "both"

    def test_returns_201_when_logged_at_is_provided(self):
        logged_at = "2024-01-01T08:00:00+00:00"
        payload = {**CARDS_PAYLOAD, "logged_at": logged_at}
        stored = {**STORED_LOG, "logged_at": logged_at}
        mock = make_mock_client(
            user_id=USER_ID,
            data=[stored],
            symptoms_ref_data=make_ref_data(CARDS_PAYLOAD["symptoms"]),
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=payload,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 201

    def test_missing_auth_header_returns_401(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    # No Authorization header
                )
        finally:
            cleanup()

        assert response.status_code == 401
        assert "Missing authorization header" in response.json()["detail"]

    def test_malformed_auth_header_returns_401(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    headers={"Authorization": "Token not-bearer-format"},
                )
        finally:
            cleanup()

        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        mock = make_mock_client(auth_error=Exception("JWT expired"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    headers={"Authorization": "Bearer expired-token"},
                )
        finally:
            cleanup()

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    def test_cards_source_with_empty_symptoms_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json={"symptoms": [], "source": "cards"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_text_source_without_free_text_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json={"symptoms": [], "source": "text"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_invalid_source_value_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json={"symptoms": ["fatigue"], "source": "unknown"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_missing_source_field_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json={"symptoms": ["fatigue"]},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    # Symptom ID validation tests

    def test_returns_400_when_symptom_ids_not_in_reference(self):
        # symptoms_ref_data returns 0 rows → all IDs invalid
        mock = make_mock_client(symptoms_ref_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "Invalid symptom IDs" in response.json()["detail"]

    def test_returns_400_when_some_symptom_ids_not_in_reference(self):
        # Only one of the two IDs exists in the reference table
        mock = make_mock_client(
            symptoms_ref_data=[{"id": CARDS_PAYLOAD["symptoms"][0]}]
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/symptoms/logs",
                    json=CARDS_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Invalid symptom IDs" in detail
        # The missing ID should be named in the error
        assert CARDS_PAYLOAD["symptoms"][1] in detail


# ---------------------------------------------------------------------------
# GET /api/symptoms/logs
# ---------------------------------------------------------------------------


class TestGetSymptomLogs:
    def test_returns_200_with_logs_list(self):
        mock = make_mock_client(
            user_id=USER_ID,
            data=[STORED_LOG],
            symptoms_ref_data=make_ref_data(STORED_LOG["symptoms"]),
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["limit"] == 50  # default
        assert len(body["logs"]) == 1
        log = body["logs"][0]
        assert log["id"] == STORED_LOG["id"]
        assert log["user_id"] == USER_ID
        # symptoms must be enriched objects, not raw strings
        assert isinstance(log["symptoms"], list)
        assert all("id" in s and "name" in s and "category" in s for s in log["symptoms"])

    def test_returns_empty_list_when_user_has_no_logs(self):
        mock = make_mock_client(user_id=USER_ID, data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/logs", headers=AUTH_HEADER)
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 0
        assert body["logs"] == []

    def test_accepts_start_date_query_param(self):
        mock = make_mock_client(user_id=USER_ID, data=[STORED_LOG])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"start_date": "2024-03-01"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_accepts_end_date_query_param(self):
        mock = make_mock_client(user_id=USER_ID, data=[STORED_LOG])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"end_date": "2024-03-31"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_accepts_start_and_end_date_query_params(self):
        mock = make_mock_client(user_id=USER_ID, data=[STORED_LOG])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"start_date": "2024-03-01", "end_date": "2024-03-31"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_custom_limit_reflected_in_response(self):
        logs = [{**STORED_LOG, "id": f"log-{i}"} for i in range(3)]
        mock = make_mock_client(user_id=USER_ID, data=logs)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"limit": 10},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.json()["limit"] == 10
        assert response.json()["count"] == 3

    def test_limit_above_max_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"limit": 101},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_limit_zero_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"limit": 0},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_missing_auth_header_returns_401(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/logs")
        finally:
            cleanup()

        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        mock = make_mock_client(auth_error=Exception("Token revoked"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    headers={"Authorization": "Bearer bad-token"},
                )
        finally:
            cleanup()

        assert response.status_code == 401

    def test_invalid_date_format_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/logs",
                    params={"start_date": "not-a-date"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_returns_all_logs_ordered_newest_first(self):
        logs = [
            {**STORED_LOG, "id": "log-1",
             "logged_at": "2024-03-15T10:00:00+00:00"},
            {**STORED_LOG, "id": "log-2",
             "logged_at": "2024-03-14T09:00:00+00:00"},
            {**STORED_LOG, "id": "log-3",
             "logged_at": "2024-03-13T08:00:00+00:00"},
        ]
        mock = make_mock_client(user_id=USER_ID, data=logs)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/logs", headers=AUTH_HEADER)
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        assert len(body["logs"]) == 3
        # First log in response should be the most recent
        assert body["logs"][0]["id"] == "log-1"

    def test_get_logs_enriches_symptom_data(self):
        """Verify symptom IDs are resolved to name+category objects via symptoms_reference."""
        symptom_ids = ["symptom-uuid-1", "symptom-uuid-2"]
        log = {**STORED_LOG, "symptoms": symptom_ids}
        ref_data = [
            {"id": "symptom-uuid-1", "name": "Hot flashes", "category": "vasomotor"},
            {"id": "symptom-uuid-2", "name": "Brain fog", "category": "cognitive"},
        ]
        mock = make_mock_client(user_id=USER_ID, data=[log], symptoms_ref_data=ref_data)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/logs", headers=AUTH_HEADER)
        finally:
            cleanup()

        assert response.status_code == 200
        symptoms = response.json()["logs"][0]["symptoms"]
        assert len(symptoms) == 2
        assert symptoms[0] == {
            "id": "symptom-uuid-1",
            "name": "Hot flashes",
            "category": "vasomotor",
        }
        assert symptoms[1] == {
            "id": "symptom-uuid-2",
            "name": "Brain fog",
            "category": "cognitive",
        }

    def test_get_logs_uses_fallback_for_unknown_symptom_id(self):
        """An ID absent from symptoms_reference falls back to id/unknown rather than failing."""
        log = {**STORED_LOG, "symptoms": ["orphan-id"]}
        mock = make_mock_client(user_id=USER_ID, data=[log], symptoms_ref_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/logs", headers=AUTH_HEADER)
        finally:
            cleanup()

        assert response.status_code == 200
        symptoms = response.json()["logs"][0]["symptoms"]
        assert len(symptoms) == 1
        assert symptoms[0]["id"] == "orphan-id"
        assert symptoms[0]["category"] == "unknown"


# ---------------------------------------------------------------------------
# GET /api/symptoms/stats/frequency
# ---------------------------------------------------------------------------

SID_HOT_FLASH = "uuid-hot-flash"
SID_BRAIN_FOG = "uuid-brain-fog"
SID_FATIGUE = "uuid-fatigue"

SYMPTOM_LOGS_DATA = [
    {"symptoms": [SID_HOT_FLASH, SID_BRAIN_FOG]},
    {"symptoms": [SID_HOT_FLASH, SID_FATIGUE]},
    {"symptoms": [SID_HOT_FLASH]},
]

SYMPTOMS_REF_DATA = [
    {"id": SID_HOT_FLASH, "name": "Hot flashes", "category": "vasomotor"},
    {"id": SID_BRAIN_FOG, "name": "Brain fog", "category": "cognitive"},
    {"id": SID_FATIGUE, "name": "Fatigue", "category": "sleep"},
]


class TestGetFrequencyStats:
    def test_frequency_stats_success(self):
        mock = make_mock_client(
            user_id=USER_ID,
            data=SYMPTOM_LOGS_DATA,
            symptoms_ref_data=SYMPTOMS_REF_DATA,
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency", headers=AUTH_HEADER
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["total_logs"] == 3
        assert "date_range_start" in body
        assert "date_range_end" in body

        stats = body["stats"]
        assert len(stats) == 3
        # Hot flashes appeared 3 times — must be first
        assert stats[0]["symptom_name"] == "Hot flashes"
        assert stats[0]["count"] == 3
        assert stats[0]["category"] == "vasomotor"
        # Remaining two each appeared once
        counts = {s["symptom_name"]: s["count"] for s in stats}
        assert counts["Brain fog"] == 1
        assert counts["Fatigue"] == 1

    def test_frequency_stats_with_date_range(self):
        mock = make_mock_client(
            user_id=USER_ID,
            data=SYMPTOM_LOGS_DATA,
            symptoms_ref_data=SYMPTOMS_REF_DATA,
        )
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency",
                    params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["date_range_start"] == "2024-01-01"
        assert body["date_range_end"] == "2024-01-31"

    def test_frequency_stats_requires_auth(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get("/api/symptoms/stats/frequency")
        finally:
            cleanup()

        assert response.status_code == 401

    def test_frequency_stats_invalid_token_returns_401(self):
        mock = make_mock_client(auth_error=Exception("Token invalid"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency",
                    headers={"Authorization": "Bearer bad-token"},
                )
        finally:
            cleanup()

        assert response.status_code == 401

    def test_frequency_stats_invalid_date_format_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency",
                    params={"start_date": "not-a-date"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_frequency_stats_start_after_end_returns_400(self):
        mock = make_mock_client(user_id=USER_ID, data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency",
                    params={"start_date": "2024-02-01", "end_date": "2024-01-01"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "start_date" in response.json()["detail"]

    def test_frequency_stats_empty_result(self):
        mock = make_mock_client(user_id=USER_ID, data=[], symptoms_ref_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency", headers=AUTH_HEADER
                )
        finally:
            cleanup()

        assert response.status_code == 200
        body = response.json()
        assert body["stats"] == []
        assert body["total_logs"] == 0

    def test_frequency_stats_sorted_by_count_descending(self):
        # Three logs: fatigue appears twice, brain_fog once
        logs = [
            {"symptoms": [SID_FATIGUE]},
            {"symptoms": [SID_FATIGUE, SID_BRAIN_FOG]},
        ]
        ref = [
            {"id": SID_FATIGUE, "name": "Fatigue", "category": "sleep"},
            {"id": SID_BRAIN_FOG, "name": "Brain fog", "category": "cognitive"},
        ]
        mock = make_mock_client(user_id=USER_ID, data=logs, symptoms_ref_data=ref)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency", headers=AUTH_HEADER
                )
        finally:
            cleanup()

        assert response.status_code == 200
        stats = response.json()["stats"]
        assert stats[0]["symptom_name"] == "Fatigue"
        assert stats[0]["count"] == 2
        assert stats[1]["symptom_name"] == "Brain fog"
        assert stats[1]["count"] == 1

    def test_frequency_stats_omits_unknown_symptom_ids(self):
        # Symptom ID in logs but absent from reference — should not appear in output
        orphan_id = "orphan-uuid-not-in-ref"
        logs = [{"symptoms": [SID_HOT_FLASH, orphan_id]}]
        ref = [{"id": SID_HOT_FLASH, "name": "Hot flashes", "category": "vasomotor"}]
        mock = make_mock_client(user_id=USER_ID, data=logs, symptoms_ref_data=ref)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/symptoms/stats/frequency", headers=AUTH_HEADER
                )
        finally:
            cleanup()

        assert response.status_code == 200
        stats = response.json()["stats"]
        assert len(stats) == 1
        assert stats[0]["symptom_id"] == SID_HOT_FLASH
