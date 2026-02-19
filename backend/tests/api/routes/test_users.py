"""Tests for POST /api/users/onboarding.

All Supabase calls are mocked via FastAPI's dependency_overrides so no
real network connections are made.
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.core.supabase import get_client
from app.main import app


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockQueryBuilder:
    """Fluent builder mock supporting select and insert on the users table.

    Tracks whether .insert() was called so execute() can return the right data.
    """

    def __init__(self, select_data=None, insert_data=None):
        self._select_data = select_data if select_data is not None else []
        self._insert_data = insert_data if insert_data is not None else []
        self._is_insert = False

    def insert(self, *_, **__):
        self._is_insert = True
        return self

    def select(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    async def execute(self):
        result = MagicMock()
        result.data = self._insert_data if self._is_insert else self._select_data
        return result


def make_mock_client(
    user_id: str = "test-user-uuid",
    email: str = "user@example.com",
    existing_user_data=None,
    insert_data=None,
    auth_error: Exception | None = None,
    admin_error: Exception | None = None,
) -> MagicMock:
    """Build a mock Supabase client for onboarding tests.

    Args:
        existing_user_data: Rows returned by the duplicate-check select.
            Pass [] for no existing user, [...] to simulate a duplicate.
        insert_data: Rows returned after the insert.
        auth_error: If set, client.auth.get_user raises this exception.
        admin_error: If set, client.auth.admin.get_user_by_id raises this.
    """
    mock = MagicMock()

    if auth_error:
        mock.auth.get_user = AsyncMock(side_effect=auth_error)
    else:
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id=user_id))
        )

    if admin_error:
        mock.auth.admin.get_user_by_id = AsyncMock(side_effect=admin_error)
    else:
        mock.auth.admin.get_user_by_id = AsyncMock(
            return_value=MagicMock(user=MagicMock(email=email))
        )

    def table_side_effect(table_name):
        return MockQueryBuilder(
            select_data=existing_user_data if existing_user_data is not None else [],
            insert_data=insert_data if insert_data is not None else [],
        )

    mock.table.side_effect = table_side_effect
    return mock


# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
EMAIL = "user@example.com"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

STORED_USER = {
    "id": USER_ID,
    "email": EMAIL,
    "date_of_birth": "1975-06-15",
    "journey_stage": "perimenopause",
    "onboarding_completed": True,
    "created_at": "2024-03-15T10:00:00+00:00",
}

VALID_PAYLOAD = {
    "date_of_birth": "1975-06-15",
    "journey_stage": "perimenopause",
}


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/users/onboarding
# ---------------------------------------------------------------------------


class TestOnboarding:
    def test_onboarding_success(self):
        mock = make_mock_client(insert_data=[STORED_USER])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == USER_ID
        assert body["email"] == EMAIL
        assert body["journey_stage"] == "perimenopause"
        assert body["onboarding_completed"] is True
        assert body["date_of_birth"] == "1975-06-15"

    def test_onboarding_success_all_journey_stages(self):
        for stage in ("perimenopause", "menopause", "post-menopause", "unsure"):
            stored = {**STORED_USER, "journey_stage": stage}
            mock = make_mock_client(insert_data=[stored])
            cleanup = override(mock)
            try:
                with TestClient(app) as client:
                    response = client.post(
                        "/api/users/onboarding",
                        json={**VALID_PAYLOAD, "journey_stage": stage},
                        headers=AUTH_HEADER,
                    )
            finally:
                cleanup()

            assert response.status_code == 201, f"Expected 201 for journey_stage={stage!r}"
            assert response.json()["journey_stage"] == stage

    def test_onboarding_requires_auth(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json=VALID_PAYLOAD,
                    # No Authorization header
                )
        finally:
            cleanup()

        assert response.status_code == 401
        assert "Missing authorization header" in response.json()["detail"]

    def test_onboarding_rejects_invalid_token(self):
        mock = make_mock_client(auth_error=Exception("JWT expired"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json=VALID_PAYLOAD,
                    headers={"Authorization": "Bearer expired-token"},
                )
        finally:
            cleanup()

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    def test_onboarding_rejects_underage(self):
        today = date.today()
        # A person born 17 years ago is always under 18
        underage_dob = date(today.year - 17, 1, 1).isoformat()
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"date_of_birth": underage_dob, "journey_stage": "unsure"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "18" in response.json()["detail"]

    def test_onboarding_rejects_future_date(self):
        from datetime import timedelta

        future_dob = (date.today() + timedelta(days=1)).isoformat()
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"date_of_birth": future_dob, "journey_stage": "unsure"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400
        assert "past" in response.json()["detail"]

    def test_onboarding_rejects_today_as_dob(self):
        today_dob = date.today().isoformat()
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"date_of_birth": today_dob, "journey_stage": "unsure"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 400

    def test_onboarding_rejects_invalid_journey_stage(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"date_of_birth": "1975-06-15", "journey_stage": "early-menopause"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_onboarding_prevents_duplicate(self):
        mock = make_mock_client(existing_user_data=[{"id": USER_ID}])
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_onboarding_returns_500_when_admin_auth_fails(self):
        mock = make_mock_client(admin_error=Exception("Auth service unavailable"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 500

    def test_onboarding_missing_date_of_birth_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"journey_stage": "perimenopause"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422

    def test_onboarding_missing_journey_stage_returns_422(self):
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/users/onboarding",
                    json={"date_of_birth": "1975-06-15"},
                    headers=AUTH_HEADER,
                )
        finally:
            cleanup()

        assert response.status_code == 422
