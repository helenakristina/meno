"""Tests for POST /api/export/pdf, POST /api/export/csv, GET /api/export/history.

Route-level tests: verify auth, request validation, and that the service layer is
called correctly. Business logic (CSV content, PDF bytes) is tested in
test_export_service.py.
"""
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_export_service, get_llm_service
from app.core.supabase import get_client
from app.main import app
from app.models.export import ExportResponse
from app.services.llm import LLMService

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


MOCK_EXPORT_RESPONSE_PDF = ExportResponse(
    signed_url="https://storage.example.com/export.pdf",
    filename="meno-summary-2024-03-01-2024-03-31.pdf",
    export_type="pdf",
)

MOCK_EXPORT_RESPONSE_CSV = ExportResponse(
    signed_url="https://storage.example.com/export.csv",
    filename="meno-logs-2024-03-01-2024-03-31.csv",
    export_type="csv",
)


def _mock_export_service(pdf_response=MOCK_EXPORT_RESPONSE_PDF, csv_response=MOCK_EXPORT_RESPONSE_CSV):
    svc = AsyncMock()
    svc.export_as_pdf.return_value = pdf_response
    svc.export_as_csv.return_value = csv_response
    svc.get_export_history.return_value = {
        "exports": [],
        "total": 0,
        "has_more": False,
        "limit": 50,
        "offset": 0,
    }
    return svc


class TestPdfExport:
    def test_pdf_export_success(self):
        mock = make_mock_client()
        cleanup = override(mock)
        mock_svc = _mock_export_service()
        app.dependency_overrides[get_export_service] = lambda: mock_svc

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["export_type"] == "pdf"
        assert "signed_url" in body
        assert "filename" in body
        mock_svc.export_as_pdf.assert_called_once()

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

    def test_pdf_generation_delegates_to_service(self):
        """Route delegates to ExportService.export_as_pdf — no direct LLM calls in route."""
        mock = make_mock_client()
        cleanup = override(mock)
        mock_svc = _mock_export_service()
        app.dependency_overrides[get_export_service] = lambda: mock_svc

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/pdf",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()
            app.dependency_overrides.clear()

        assert response.status_code == 200
        mock_svc.export_as_pdf.assert_called_once()

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
        mock_svc = _mock_export_service()
        app.dependency_overrides[get_export_service] = lambda: mock_svc

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["export_type"] == "csv"
        assert "signed_url" in body
        mock_svc.export_as_csv.assert_called_once()

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
        """Route delegates CSV logic to ExportService — multiple-log scenarios in service tests."""
        mock = make_mock_client()
        cleanup = override(mock)
        mock_svc = _mock_export_service()
        app.dependency_overrides[get_export_service] = lambda: mock_svc

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["export_type"] == "csv"

    def test_csv_log_with_no_symptoms(self):
        """Route delegates log rendering to ExportService — content tested in service tests."""
        mock = make_mock_client()
        cleanup = override(mock)
        mock_svc = _mock_export_service()
        app.dependency_overrides[get_export_service] = lambda: mock_svc

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/export/csv",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()
            app.dependency_overrides.clear()

        assert response.status_code == 200
