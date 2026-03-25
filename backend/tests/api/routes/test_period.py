"""Tests for period tracking routes."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_period_service
from app.core.supabase import get_client
from app.main import app
from app.models.period import (
    CreatePeriodLogResponse,
    CycleAnalysisResponse,
    PeriodLogListResponse,
    PeriodLogResponse,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
LOG_ID = "log-uuid-1"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

LOG_CREATED_AT = "2026-03-16T10:00:00+00:00"

PERIOD_LOG = PeriodLogResponse(
    id=LOG_ID,
    period_start=date(2026, 3, 1),
    period_end=None,
    flow_level="medium",
    notes=None,
    cycle_length=28,
    created_at=datetime(2026, 3, 16, tzinfo=timezone.utc),
)

CYCLE_ANALYSIS = CycleAnalysisResponse(
    average_cycle_length=28.0,
    cycle_variability=2.1,
    months_since_last_period=0,
    inferred_stage=None,
    has_sufficient_data=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_auth_client(user_id: str = USER_ID) -> MagicMock:
    mock = MagicMock()
    mock.auth.get_user = AsyncMock(return_value=MagicMock(user=MagicMock(id=user_id)))
    return mock


def override_service(mock_service):
    app.dependency_overrides[get_period_service] = lambda: mock_service


def override_auth(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client


def clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/period/logs
# ---------------------------------------------------------------------------


class TestCreatePeriodLog:
    def test_create_log_success(self):
        mock_service = MagicMock()
        mock_service.create_log = AsyncMock(
            return_value=CreatePeriodLogResponse(log=PERIOD_LOG, bleeding_alert=False)
        )
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={"period_start": "2026-03-01", "flow_level": "medium"},
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 201
        body = response.json()
        assert body["log"]["period_start"] == "2026-03-01"
        assert body["bleeding_alert"] is False

    def test_create_log_returns_bleeding_alert_true(self):
        mock_service = MagicMock()
        mock_service.create_log = AsyncMock(
            return_value=CreatePeriodLogResponse(log=PERIOD_LOG, bleeding_alert=True)
        )
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={"period_start": "2026-03-01"},
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 201
        assert response.json()["bleeding_alert"] is True

    def test_create_log_requires_auth(self):
        mock_service = MagicMock()
        auth_client = MagicMock()
        auth_client.auth.get_user = AsyncMock(side_effect=Exception("No token"))
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={"period_start": "2026-03-01"},
                )
        finally:
            clear_overrides()

        assert response.status_code == 401

    def test_create_log_missing_period_start_returns_422(self):
        mock_service = MagicMock()
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={"flow_level": "medium"},
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 422

    def test_create_log_validates_date_order(self):
        mock_service = MagicMock()
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={
                        "period_start": "2026-03-10",
                        "period_end": "2026-03-01",  # before start
                    },
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 422

    def test_create_log_with_full_payload(self):
        mock_service = MagicMock()
        mock_service.create_log = AsyncMock(
            return_value=CreatePeriodLogResponse(log=PERIOD_LOG, bleeding_alert=False)
        )
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/period/logs",
                    json={
                        "period_start": "2026-03-01",
                        "period_end": "2026-03-05",
                        "flow_level": "heavy",
                        "notes": "Very heavy this month",
                    },
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/period/logs
# ---------------------------------------------------------------------------


class TestListPeriodLogs:
    def test_list_logs_returns_empty_list(self):
        mock_service = MagicMock()
        mock_service.get_logs = AsyncMock(return_value=PeriodLogListResponse(logs=[]))
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/logs", headers=AUTH_HEADER)
        finally:
            clear_overrides()

        assert response.status_code == 200
        assert response.json()["logs"] == []

    def test_list_logs_returns_logs(self):
        mock_service = MagicMock()
        mock_service.get_logs = AsyncMock(
            return_value=PeriodLogListResponse(logs=[PERIOD_LOG])
        )
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/logs", headers=AUTH_HEADER)
        finally:
            clear_overrides()

        assert response.status_code == 200
        assert len(response.json()["logs"]) == 1

    def test_list_logs_passes_date_params_to_service(self):
        mock_service = MagicMock()
        mock_service.get_logs = AsyncMock(return_value=PeriodLogListResponse(logs=[]))
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                client.get(
                    "/api/period/logs?start_date=2026-01-01&end_date=2026-03-31",
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        mock_service.get_logs.assert_called_once_with(
            USER_ID, "2026-01-01", "2026-03-31"
        )

    def test_list_logs_requires_auth(self):
        mock_service = MagicMock()
        auth_client = MagicMock()
        auth_client.auth.get_user = AsyncMock(side_effect=Exception("No token"))
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/logs")
        finally:
            clear_overrides()

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/period/logs/{log_id}
# ---------------------------------------------------------------------------


class TestUpdatePeriodLog:
    def test_update_log_success(self):
        updated = PERIOD_LOG.model_copy(update={"flow_level": "heavy"})
        mock_service = MagicMock()
        mock_service.update_log = AsyncMock(return_value=updated)
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.patch(
                    f"/api/period/logs/{LOG_ID}",
                    json={"flow_level": "heavy"},
                    headers=AUTH_HEADER,
                )
        finally:
            clear_overrides()

        assert response.status_code == 200
        assert response.json()["flow_level"] == "heavy"

    def test_update_log_requires_auth(self):
        mock_service = MagicMock()
        auth_client = MagicMock()
        auth_client.auth.get_user = AsyncMock(side_effect=Exception("No token"))
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.patch(
                    f"/api/period/logs/{LOG_ID}",
                    json={"flow_level": "light"},
                )
        finally:
            clear_overrides()

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/period/logs/{log_id}
# ---------------------------------------------------------------------------


class TestDeletePeriodLog:
    def test_delete_log_success(self):
        mock_service = MagicMock()
        mock_service.delete_log = AsyncMock(return_value=None)
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.delete(
                    f"/api/period/logs/{LOG_ID}", headers=AUTH_HEADER
                )
        finally:
            clear_overrides()

        assert response.status_code == 204

    def test_delete_log_requires_auth(self):
        mock_service = MagicMock()
        auth_client = MagicMock()
        auth_client.auth.get_user = AsyncMock(side_effect=Exception("No token"))
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.delete(f"/api/period/logs/{LOG_ID}")
        finally:
            clear_overrides()

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/period/analysis
# ---------------------------------------------------------------------------


class TestGetCycleAnalysis:
    def test_get_analysis_success(self):
        mock_service = MagicMock()
        mock_service.get_analysis = AsyncMock(return_value=CYCLE_ANALYSIS)
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/analysis", headers=AUTH_HEADER)
        finally:
            clear_overrides()

        assert response.status_code == 200
        body = response.json()
        assert body["average_cycle_length"] == 28.0
        assert body["has_sufficient_data"] is True

    def test_get_analysis_empty_when_no_logs(self):
        mock_service = MagicMock()
        mock_service.get_analysis = AsyncMock(
            return_value=CycleAnalysisResponse(has_sufficient_data=False)
        )
        auth_client = make_auth_client()
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/analysis", headers=AUTH_HEADER)
        finally:
            clear_overrides()

        assert response.status_code == 200
        assert response.json()["has_sufficient_data"] is False
        assert response.json()["average_cycle_length"] is None

    def test_get_analysis_requires_auth(self):
        mock_service = MagicMock()
        auth_client = MagicMock()
        auth_client.auth.get_user = AsyncMock(side_effect=Exception("No token"))
        override_service(mock_service)
        override_auth(auth_client)

        try:
            with TestClient(app) as client:
                response = client.get("/api/period/analysis")
        finally:
            clear_overrides()

        assert response.status_code == 401
