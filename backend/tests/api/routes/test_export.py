"""Tests for POST /api/export/pdf and POST /api/export/csv.

Supabase is mocked via FastAPI dependency_overrides.
LLM functions are patched so no real OpenAI calls are made.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.supabase import get_client
from app.main import app

# ---------------------------------------------------------------------------
# Mock helpers (same pattern as test_symptoms.py)
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

SAMPLE_LOG = {
    "logged_at": "2024-03-15T10:00:00+00:00",
    "symptoms": ["uuid-hot-flash", "uuid-fatigue"],
    "free_text_entry": "Feeling really tired today",
}

SAMPLE_REF = [
    {"id": "uuid-hot-flash", "name": "Hot flashes", "category": "vasomotor"},
    {"id": "uuid-fatigue", "name": "Fatigue", "category": "energy"},
]

MOCK_SUMMARY = (
    "Logs show a pattern of vasomotor symptoms throughout the tracked period. "
    "Data indicates that hot flashes and fatigue appeared together frequently. "
    "These patterns may be worth discussing with your healthcare provider."
)

MOCK_QUESTIONS = [
    "Could you help me understand why hot flashes and fatigue might occur together?",
    "What might explain the frequency of vasomotor symptoms I've been logging?",
    "How might sleep quality relate to the energy-related symptoms in my logs?",
    "Could you help me understand what the co-occurrence of these symptoms indicates?",
    "What might explain the pattern of symptoms logged during this period?",
]

VALID_PAYLOAD = {
    "date_range_start": "2024-03-01",
    "date_range_end": "2024-03-31",
}


class MockQueryBuilder:
    """Fluent builder mock that supports arbitrary chaining + async execute()."""

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


def make_mock_client(
    user_id: str = USER_ID,
    log_data=None,
    ref_data=None,
    auth_error: Exception | None = None,
) -> MagicMock:
    mock = MagicMock()

    if auth_error:
        mock.auth.get_user = AsyncMock(side_effect=auth_error)
    else:
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id=user_id))
        )

    def table_side_effect(table_name):
        if table_name == "symptom_logs":
            return MockQueryBuilder(data=log_data if log_data is not None else [SAMPLE_LOG])
        elif table_name == "symptoms_reference":
            return MockQueryBuilder(data=ref_data if ref_data is not None else SAMPLE_REF)
        else:
            # exports table — return success
            return MockQueryBuilder(data=[{"id": "export-uuid"}])

    mock.table.side_effect = table_side_effect
    return mock


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# test_pdf_export_success
# ---------------------------------------------------------------------------


class TestPdfExport:
    def test_pdf_export_success(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with (
                patch(
                    "app.api.routes.export.generate_symptom_summary",
                    new=AsyncMock(return_value=MOCK_SUMMARY),
                ),
                patch(
                    "app.api.routes.export.generate_provider_questions",
                    new=AsyncMock(return_value=MOCK_QUESTIONS),
                ),
                TestClient(app) as client,
            ):
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert ".pdf" in response.headers["content-disposition"]
        # PDF files start with the %PDF magic bytes
        assert response.content[:4] == b"%PDF"

    def test_pdf_export_requires_auth(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post("/api/export/pdf", json=VALID_PAYLOAD)
        finally:
            cleanup()

        assert response.status_code == 401

    def test_pdf_export_invalid_date_range_returns_400(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json={
                        "date_range_start": "2024-03-31",
                        "date_range_end": "2024-03-01",
                    },
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "date_range_start" in response.json()["detail"]

    def test_pdf_export_future_end_date_returns_400(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json={
                        "date_range_start": "2024-01-01",
                        "date_range_end": "2099-12-31",
                    },
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "future" in response.json()["detail"]

    def test_pdf_export_no_data_returns_400(self):
        mock = make_mock_client(log_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "No symptom logs" in response.json()["detail"]

    def test_pdf_generation_with_mocked_openai(self):
        """Verify that both LLM functions are called with frequency and co-occurrence data."""
        mock = make_mock_client(
            log_data=[SAMPLE_LOG, SAMPLE_LOG],  # Two identical logs → (A,B) co-occur 2×
            ref_data=SAMPLE_REF,
        )
        cleanup = override(mock)

        summary_mock = AsyncMock(return_value=MOCK_SUMMARY)
        questions_mock = AsyncMock(return_value=MOCK_QUESTIONS)

        try:
            with (
                patch("app.api.routes.export.generate_symptom_summary", new=summary_mock),
                patch("app.api.routes.export.generate_provider_questions", new=questions_mock),
                TestClient(app) as client,
            ):
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        # Both LLM functions must have been called
        summary_mock.assert_called_once()
        questions_mock.assert_called_once()

        # The frequency stats passed to the summary should reflect our two logs
        freq_stats, coocc_stats, date_range = summary_mock.call_args.args
        symptom_names = {s.symptom_name for s in freq_stats}
        assert "Hot flashes" in symptom_names
        assert "Fatigue" in symptom_names

    def test_pdf_export_invalid_auth_token_returns_401(self):
        mock = make_mock_client(auth_error=Exception("JWT expired"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers={"Authorization": "Bearer bad-token"},
                )
        finally:
            cleanup()

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# test_csv_export_success
# ---------------------------------------------------------------------------


class TestCsvExport:
    def test_csv_export_success(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Verify CSV structure (splitlines handles \r\n and \n)
        lines = response.text.strip().splitlines()
        assert lines[0] == "date,symptoms,free_text_notes"
        assert len(lines) == 2  # header + 1 log row

        # Verify resolved symptom names appear in the row
        data_row = lines[1]
        assert "Hot flashes" in data_row
        assert "Fatigue" in data_row
        assert "Feeling really tired today" in data_row

    def test_csv_export_requires_auth(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post("/api/export/csv", json=VALID_PAYLOAD)
        finally:
            cleanup()

        assert response.status_code == 401

    def test_csv_export_invalid_date_range_returns_400(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json={
                        "date_range_start": "2024-06-01",
                        "date_range_end": "2024-01-01",
                    },
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400

    def test_csv_export_no_data_returns_400(self):
        mock = make_mock_client(log_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400

    def test_csv_export_multiple_logs(self):
        logs = [
            {
                "logged_at": "2024-03-10T09:00:00+00:00",
                "symptoms": ["uuid-hot-flash"],
                "free_text_entry": None,
            },
            {
                "logged_at": "2024-03-15T10:00:00+00:00",
                "symptoms": ["uuid-fatigue"],
                "free_text_entry": "Very tired",
            },
        ]
        mock = make_mock_client(log_data=logs, ref_data=SAMPLE_REF)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert len(lines) == 3  # header + 2 data rows
        assert "2024-03-10" in lines[1]
        assert "Hot flashes" in lines[1]
        assert "2024-03-15" in lines[2]
        assert "Fatigue" in lines[2]
        assert "Very tired" in lines[2]

    def test_csv_log_with_no_symptoms(self):
        """A text-only log (no symptom IDs) produces an empty symptoms column."""
        logs = [
            {
                "logged_at": "2024-03-15T10:00:00+00:00",
                "symptoms": [],
                "free_text_entry": "Feeling off today",
            }
        ]
        mock = make_mock_client(log_data=logs, ref_data=[])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert len(lines) == 2
        # symptoms column should be empty, free text should be present
        assert "Feeling off today" in lines[1]
