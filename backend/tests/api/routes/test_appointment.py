"""Tests for POST /api/appointment-prep/context.

All Supabase calls are mocked via FastAPI's dependency_overrides so no
real network connections are made.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.core.supabase import get_client
from app.main import app


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockQueryBuilder:
    """Fluent builder mock supporting insert and select on appointment tables.

    Tracks the last mutating operation so execute() returns the right data.
    """

    def __init__(
        self,
        select_data=None,
        insert_data=None,
        insert_error=None,
    ):
        self._select_data = select_data if select_data is not None else []
        self._insert_data = insert_data if insert_data is not None else []
        self._insert_error = insert_error
        self._op: str = "select"

    def insert(self, *_, **__):
        self._op = "insert"
        return self

    def select(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    async def execute(self):
        if self._op == "insert" and self._insert_error:
            raise self._insert_error
        result = MagicMock()
        if self._op == "insert":
            result.data = self._insert_data
        else:
            result.data = self._select_data
        return result


def make_mock_client(
    created_context_id: str = "550e8400-e29b-41d4-a716-446655440000",
    insert_data=None,
    insert_error: Exception | None = None,
    auth_error: Exception | None = None,
) -> MagicMock:
    """Build a mock Supabase client for appointment endpoint tests.

    Args:
        created_context_id: ID returned when creating new context.
        insert_data: Rows returned after insert operations.
        insert_error: If set, insert().execute() raises this exception.
        auth_error: If set, client.auth.get_user raises this exception.
    """
    mock = MagicMock()

    if auth_error:
        mock.auth.get_user = AsyncMock(side_effect=auth_error)
    else:
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id="test-user-uuid"))
        )

    if insert_data is None:
        insert_data = [
            {
                "id": created_context_id,
                "user_id": "test-user-uuid",
                "appointment_type": "new_provider",
                "goal": "explore_hrt",
                "dismissed_before": "once_or_twice",
            }
        ]

    def table_side_effect(table_name):
        return MockQueryBuilder(
            insert_data=insert_data,
            insert_error=insert_error,
        )

    mock.table.side_effect = table_side_effect
    return mock


# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

VALID_PAYLOAD = {
    "appointment_type": "new_provider",
    "goal": "explore_hrt",
    "dismissed_before": "once_or_twice",
}

CONTEXT_ID = "550e8400-e29b-41d4-a716-446655440000"


def override(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    return lambda: app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/appointment-prep/context
# ---------------------------------------------------------------------------


class TestCreateAppointmentContext:
    def test_create_context_success(self):
        """Test creating appointment context successfully."""
        mock = make_mock_client(created_context_id=CONTEXT_ID)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 201
            data = response.json()
            assert data["appointment_id"] == CONTEXT_ID
            assert data["next_step"] == "narrative"
        finally:
            cleanup()

    def test_create_context_invalid_appointment_type(self):
        """Test creating context with invalid appointment_type enum."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                payload = {
                    "appointment_type": "invalid_type",
                    "goal": "explore_hrt",
                    "dismissed_before": "once_or_twice",
                }
                response = client.post(
                    "/api/appointment-prep/context",
                    json=payload,
                    headers=AUTH_HEADER,
                )

            # Pydantic validation error
            assert response.status_code == 422
        finally:
            cleanup()

    def test_create_context_invalid_goal(self):
        """Test creating context with invalid goal enum."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                payload = {
                    "appointment_type": "new_provider",
                    "goal": "invalid_goal",
                    "dismissed_before": "once_or_twice",
                }
                response = client.post(
                    "/api/appointment-prep/context",
                    json=payload,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 422
        finally:
            cleanup()

    def test_create_context_invalid_dismissed_before(self):
        """Test creating context with invalid dismissed_before enum."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                payload = {
                    "appointment_type": "new_provider",
                    "goal": "explore_hrt",
                    "dismissed_before": "invalid",
                }
                response = client.post(
                    "/api/appointment-prep/context",
                    json=payload,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 422
        finally:
            cleanup()

    def test_create_context_missing_auth_header(self):
        """Test creating context without authentication header."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    # No auth header
                )

            assert response.status_code == 401
            assert "Missing authorization header" in response.json()["detail"]
        finally:
            cleanup()

    def test_create_context_invalid_auth_header_format(self):
        """Test creating context with malformed authorization header."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    headers={"Authorization": "InvalidFormat token"},
                )

            assert response.status_code == 401
            assert "Invalid authorization header format" in response.json()["detail"]
        finally:
            cleanup()

    def test_create_context_invalid_token(self):
        """Test creating context with invalid JWT token."""
        mock = make_mock_client(auth_error=Exception("Invalid token"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    headers={"Authorization": "Bearer invalid-token"},
                )

            assert response.status_code == 401
            assert "Invalid or expired token" in response.json()["detail"]
        finally:
            cleanup()

    def test_create_context_db_error(self):
        """Test creating context when database operation fails."""
        mock = make_mock_client(insert_error=Exception("DB connection error"))
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 500
            assert "Database error occurred" in response.json()["detail"]
        finally:
            cleanup()

    def test_create_context_all_appointment_types(self):
        """Test creating context with each valid appointment_type."""
        types = ["new_provider", "established_relationship"]
        for appt_type in types:
            mock = make_mock_client()
            cleanup = override(mock)
            try:
                with TestClient(app) as client:
                    payload = {
                        "appointment_type": appt_type,
                        "goal": "explore_hrt",
                        "dismissed_before": "once_or_twice",
                    }
                    response = client.post(
                        "/api/appointment-prep/context",
                        json=payload,
                        headers=AUTH_HEADER,
                    )

                assert response.status_code == 201
                assert response.json()["appointment_id"] == CONTEXT_ID
            finally:
                cleanup()

    def test_create_context_all_goals(self):
        """Test creating context with each valid goal."""
        goals = [
            "assess_status",
            "explore_hrt",
            "optimize_current_treatment",
            "urgent_symptom",
        ]
        for goal in goals:
            mock = make_mock_client()
            cleanup = override(mock)
            try:
                with TestClient(app) as client:
                    payload = {
                        "appointment_type": "new_provider",
                        "goal": goal,
                        "dismissed_before": "once_or_twice",
                    }
                    response = client.post(
                        "/api/appointment-prep/context",
                        json=payload,
                        headers=AUTH_HEADER,
                    )

                assert response.status_code == 201
            finally:
                cleanup()

    def test_create_context_all_dismissal_experiences(self):
        """Test creating context with each valid dismissal_experience."""
        experiences = ["no", "once_or_twice", "multiple_times"]
        for experience in experiences:
            mock = make_mock_client()
            cleanup = override(mock)
            try:
                with TestClient(app) as client:
                    payload = {
                        "appointment_type": "new_provider",
                        "goal": "explore_hrt",
                        "dismissed_before": experience,
                    }
                    response = client.post(
                        "/api/appointment-prep/context",
                        json=payload,
                        headers=AUTH_HEADER,
                    )

                assert response.status_code == 201
            finally:
                cleanup()

    def test_create_context_missing_required_fields(self):
        """Test creating context without required fields."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                # Missing dismissed_before
                payload = {
                    "appointment_type": "new_provider",
                    "goal": "explore_hrt",
                }
                response = client.post(
                    "/api/appointment-prep/context",
                    json=payload,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 422
        finally:
            cleanup()

    def test_create_context_response_format(self):
        """Test that response has correct format and fields."""
        mock = make_mock_client(created_context_id=CONTEXT_ID)
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/context",
                    json=VALID_PAYLOAD,
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 201
            data = response.json()

            # Verify response structure
            assert "appointment_id" in data
            assert "next_step" in data
            assert isinstance(data["appointment_id"], str)
            assert isinstance(data["next_step"], str)
            assert len(data["appointment_id"]) > 0
            assert data["next_step"] == "narrative"
        finally:
            cleanup()


# ============================================================================
# POST /api/appointment-prep/{id}/narrative (Step 2)
# ============================================================================


class TestGenerateAppointmentNarrative:
    """Tests for POST /api/appointment-prep/{id}/narrative endpoint."""

    def test_generate_narrative_no_logs(self):
        """Test generating narrative when user has no symptom logs."""
        mock = MagicMock()
        mock.auth.get_user = AsyncMock(
            return_value=MagicMock(user=MagicMock(id="test-user-uuid"))
        )

        def table_side_effect(table_name):
            builder = MagicMock()

            if table_name == "appointment_prep_contexts":
                # Handle both select (for get_context) and update (for save_narrative)
                builder.select.return_value = builder
                builder.update.return_value = builder
                builder.eq.return_value = builder
                builder.execute = AsyncMock(
                    return_value=MagicMock(
                        data=[
                            {
                                "id": CONTEXT_ID,
                                "user_id": "test-user-uuid",
                                "appointment_type": "new_provider",
                                "goal": "explore_hrt",
                                "dismissed_before": "once_or_twice",
                                "narrative": None,
                            }
                        ]
                    )
                )
            elif table_name == "users":
                builder.select.return_value = builder
                builder.eq.return_value = builder
                builder.execute = AsyncMock(
                    return_value=MagicMock(
                        data=[
                            {
                                "id": "test-user-uuid",
                                "journey_stage": "perimenopause",
                                "age": 48,
                            }
                        ]
                    )
                )
            elif table_name == "symptom_logs":
                builder.select.return_value = builder
                builder.eq.return_value = builder
                builder.gte.return_value = builder
                builder.lte.return_value = builder
                builder.order.return_value = builder
                builder.limit.return_value = builder
                builder.execute = AsyncMock(return_value=MagicMock(data=[]))

            return builder

        mock.table.side_effect = table_side_effect

        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/appointment-prep/{CONTEXT_ID}/narrative",
                    json={"days_back": 60},
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 200
            data = response.json()
            assert "No symptom logs found" in data["narrative"]
            assert data["next_step"] == "prioritize"
        finally:
            cleanup()

    def test_generate_narrative_invalid_days_back(self):
        """Test generating narrative with invalid days_back (> 365)."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/appointment-prep/{CONTEXT_ID}/narrative",
                    json={"days_back": 400},  # Invalid: > 365
                    headers=AUTH_HEADER,
                )

            # Pydantic validation should reject days_back > 365
            assert response.status_code == 422
        finally:
            cleanup()

    def test_generate_narrative_appointment_not_found(self):
        """Test generating narrative for non-existent appointment."""
        # Create a mock that returns empty data for get_context query
        mock = make_mock_client()

        def custom_table(*args, **kwargs):
            builder = MagicMock()
            builder.select.return_value = builder
            builder.eq.return_value = builder
            builder.gte.return_value = builder
            builder.lte.return_value = builder
            builder.order.return_value = builder
            builder.limit.return_value = builder
            builder.update.return_value = builder
            builder.in_.return_value = builder
            # Return empty data for appointment_prep_contexts queries
            builder.execute = AsyncMock(return_value=MagicMock(data=[]))
            return builder

        mock.table = custom_table

        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/appointment-prep/nonexistent-id/narrative",
                    json={"days_back": 60},
                    headers=AUTH_HEADER,
                )

            assert response.status_code == 404
        finally:
            cleanup()

    def test_generate_narrative_missing_auth(self):
        """Test generating narrative without authentication header."""
        mock = make_mock_client()
        cleanup = override(mock)
        try:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/appointment-prep/{CONTEXT_ID}/narrative",
                    json={"days_back": 60},
                    # No auth header
                )

            assert response.status_code == 401
            assert "Missing authorization header" in response.json()["detail"]
        finally:
            cleanup()
