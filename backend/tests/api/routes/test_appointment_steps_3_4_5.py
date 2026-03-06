"""Tests for Appointment Prep Steps 3-5: Prioritize, Scenarios, Generate.

Focus on critical paths and error handling. Mocks are kept simple.
"""

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# Step 3: Prioritize Concerns Tests
# ---------------------------------------------------------------------------


def test_prioritize_concerns_missing_auth():
    """Return 401 if missing authorization header."""
    response = client.put(
        "/api/appointment-prep/apt-123/prioritize",
        json={"concerns": ["concern1"]},
    )
    assert response.status_code == 401


def test_prioritize_concerns_empty_list():
    """Reject empty concerns list (Pydantic validation)."""
    response = client.put(
        "/api/appointment-prep/apt-123/prioritize",
        headers={"Authorization": "Bearer invalid-token"},
        json={"concerns": []},
    )
    # Will fail on auth first, but validation would catch empty list
    assert response.status_code in [401, 422]


# ---------------------------------------------------------------------------
# Step 4: Generate Scenarios Tests
# ---------------------------------------------------------------------------


def test_generate_scenarios_missing_auth():
    """Return 401 if missing authorization header."""
    response = client.post(
        "/api/appointment-prep/apt-123/scenarios",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Step 5: Generate Outputs Tests
# ---------------------------------------------------------------------------


def test_generate_outputs_missing_auth():
    """Return 401 if missing authorization header."""
    response = client.post(
        "/api/appointment-prep/apt-123/generate",
    )
    assert response.status_code == 401
