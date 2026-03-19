"""Tests for medication tracking routes."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_medication_service
from app.core.supabase import get_client
from app.main import app
from app.models.medications import (
    MedicationChangeDoseResponse,
    MedicationReferenceResult,
    MedicationResponse,
    SymptomComparisonResponse,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid"
MED_ID = "med-uuid-1"
AUTH_HEADER = {"Authorization": "Bearer valid-jwt-token"}

_MED = MedicationResponse(
    id=MED_ID,
    medication_ref_id=None,
    medication_name="Estradiol",
    dose="1mg",
    delivery_method="patch",
    frequency="twice_weekly",
    start_date=date(2026, 1, 1),
    end_date=None,
    previous_entry_id=None,
    notes=None,
)

_REF = MedicationReferenceResult(
    id="ref-1",
    brand_name="Estrogel",
    generic_name="estradiol",
    hormone_type="estrogen",
    common_forms=["gel"],
    common_doses=["0.75mg"],
    notes=None,
    is_user_created=False,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_auth_client(user_id: str = USER_ID) -> MagicMock:
    mock = MagicMock()
    mock.auth.get_user = AsyncMock(
        return_value=MagicMock(user=MagicMock(id=user_id))
    )
    return mock


def override_service(mock_service):
    app.dependency_overrides[get_medication_service] = lambda: mock_service


def override_auth(mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client


def clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/medications/reference
# ---------------------------------------------------------------------------


class TestSearchReference:
    def test_search_reference_returns_list(self):
        mock_service = MagicMock()
        mock_service.search_reference = AsyncMock(return_value=[_REF])
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get("/api/medications/reference?search=estro", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 200
        assert resp.json()[0]["generic_name"] == "estradiol"

    def test_search_reference_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get("/api/medications/reference")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/medications/reference
# ---------------------------------------------------------------------------


class TestCreateReference:
    def test_create_reference_returns_201(self):
        mock_service = MagicMock()
        mock_service.create_reference_entry = AsyncMock(return_value=_REF)
        override_service(mock_service)
        override_auth(make_auth_client())

        payload = {
            "generic_name": "custom estrogen",
            "hormone_type": "estrogen",
            "common_forms": [],
            "common_doses": [],
        }
        with TestClient(app) as client:
            resp = client.post("/api/medications/reference", json=payload, headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/medications/current
# ---------------------------------------------------------------------------


class TestGetCurrentMedications:
    def test_get_current_returns_active_medications(self):
        mock_service = MagicMock()
        mock_service.list_current = AsyncMock(return_value=[_MED])
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get("/api/medications/current", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 200
        assert resp.json()[0]["medication_name"] == "Estradiol"

    def test_get_current_returns_empty_when_disabled(self):
        mock_service = MagicMock()
        mock_service.list_current = AsyncMock(return_value=[])
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get("/api/medications/current", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_current_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get("/api/medications/current")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/medications (list all)
# ---------------------------------------------------------------------------


class TestListMedications:
    def test_list_all_returns_200(self):
        mock_service = MagicMock()
        mock_service.list = AsyncMock(return_value=[_MED])
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get("/api/medications", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# POST /api/medications
# ---------------------------------------------------------------------------


class TestCreateMedication:
    def test_create_returns_201(self):
        mock_service = MagicMock()
        mock_service.create = AsyncMock(return_value=_MED)
        override_service(mock_service)
        override_auth(make_auth_client())

        payload = {
            "medication_name": "Estradiol",
            "dose": "1mg",
            "delivery_method": "patch",
            "start_date": "2026-01-01",
        }
        with TestClient(app) as client:
            resp = client.post("/api/medications", json=payload, headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 201
        assert resp.json()["medication_name"] == "Estradiol"

    def test_create_returns_400_on_validation_error(self):
        from app.exceptions import ValidationError as DomainValidationError

        mock_service = MagicMock()
        mock_service.create = AsyncMock(side_effect=DomainValidationError("future date"))
        override_service(mock_service)
        override_auth(make_auth_client())

        payload = {
            "medication_name": "Estradiol",
            "dose": "1mg",
            "delivery_method": "patch",
            "start_date": "2026-01-01",
        }
        with TestClient(app) as client:
            resp = client.post("/api/medications", json=payload, headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 400

    def test_create_requires_auth(self):
        with TestClient(app) as client:
            resp = client.post("/api/medications", json={})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/medications/{id}
# ---------------------------------------------------------------------------


class TestGetMedication:
    def test_get_returns_medication(self):
        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=_MED)
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get(f"/api/medications/{MED_ID}", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 200
        assert resp.json()["id"] == MED_ID

    def test_get_returns_404_when_not_found(self):
        from app.exceptions import EntityNotFoundError

        mock_service = MagicMock()
        mock_service.get = AsyncMock(side_effect=EntityNotFoundError("not found"))
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get("/api/medications/nonexistent", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/medications/{id}
# ---------------------------------------------------------------------------


class TestUpdateMedication:
    def test_update_returns_200(self):
        mock_service = MagicMock()
        mock_service.update = AsyncMock(return_value=_MED)
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.put(
                f"/api/medications/{MED_ID}",
                json={"notes": "updated"},
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 200

    def test_update_returns_400_on_validation_error(self):
        from app.exceptions import ValidationError as DomainValidationError

        mock_service = MagicMock()
        mock_service.update = AsyncMock(side_effect=DomainValidationError("bad end date"))
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.put(
                f"/api/medications/{MED_ID}",
                json={"end_date": "2025-01-01"},
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/medications/{id}/change
# ---------------------------------------------------------------------------


class TestChangeDose:
    def test_change_dose_returns_200(self):
        mock_service = MagicMock()
        mock_service.change_dose = AsyncMock(
            return_value=MedicationChangeDoseResponse(
                previous_medication_id=MED_ID,
                new_medication_id="new-id",
            )
        )
        override_service(mock_service)
        override_auth(make_auth_client())

        payload = {
            "dose": "2mg",
            "delivery_method": "gel",
            "effective_date": "2026-03-01",
        }
        with TestClient(app) as client:
            resp = client.post(
                f"/api/medications/{MED_ID}/change",
                json=payload,
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 201
        assert resp.json()["new_medication_id"] == "new-id"

    def test_change_dose_returns_400_on_validation_error(self):
        from app.exceptions import ValidationError as DomainValidationError

        mock_service = MagicMock()
        mock_service.change_dose = AsyncMock(
            side_effect=DomainValidationError("effective date before start")
        )
        override_service(mock_service)
        override_auth(make_auth_client())

        payload = {
            "dose": "2mg",
            "delivery_method": "gel",
            "effective_date": "2025-01-01",
        }
        with TestClient(app) as client:
            resp = client.post(
                f"/api/medications/{MED_ID}/change",
                json=payload,
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/medications/{id}
# ---------------------------------------------------------------------------


class TestDeleteMedication:
    def test_delete_returns_204(self):
        mock_service = MagicMock()
        mock_service.delete = AsyncMock(return_value=None)
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.delete(f"/api/medications/{MED_ID}", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 204

    def test_delete_returns_404_when_not_found(self):
        from app.exceptions import EntityNotFoundError

        mock_service = MagicMock()
        mock_service.delete = AsyncMock(side_effect=EntityNotFoundError("not found"))
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.delete("/api/medications/nonexistent", headers=AUTH_HEADER)

        clear_overrides()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/medications/{id}/symptom-comparison
# ---------------------------------------------------------------------------


class TestSymptomComparison:
    def test_comparison_returns_200(self):
        mock_service = MagicMock()
        mock_service.get_symptom_comparison = AsyncMock(
            return_value=SymptomComparisonResponse(
                medication_id=MED_ID,
                medication_name="Estradiol",
                dose="1mg",
                delivery_method="patch",
                start_date=date(2026, 1, 1),
                rows=[],
                has_confounding_changes=False,
            )
        )
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get(
                f"/api/medications/{MED_ID}/symptom-comparison",
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 200
        assert resp.json()["medication_id"] == MED_ID

    def test_comparison_returns_404_when_medication_not_found(self):
        from app.exceptions import EntityNotFoundError

        mock_service = MagicMock()
        mock_service.get_symptom_comparison = AsyncMock(
            side_effect=EntityNotFoundError("not found")
        )
        override_service(mock_service)
        override_auth(make_auth_client())

        with TestClient(app) as client:
            resp = client.get(
                "/api/medications/nonexistent/symptom-comparison",
                headers=AUTH_HEADER,
            )

        clear_overrides()
        assert resp.status_code == 404

    def test_comparison_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get(f"/api/medications/{MED_ID}/symptom-comparison")
        assert resp.status_code == 401
