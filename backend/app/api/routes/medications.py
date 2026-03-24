"""HTTP routes for MHT medication tracking."""

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, get_medication_service
from app.models.medications import (
    MedicationChangeDose,
    MedicationChangeDoseResponse,
    MedicationCreate,
    MedicationReferenceCreate,
    MedicationReferenceResult,
    MedicationResponse,
    MedicationUpdate,
    SymptomComparisonResponse,
)
from app.services.medication_base import MedicationServiceBase

router = APIRouter(prefix="/api/medications", tags=["medications"])


# ---------------------------------------------------------------------------
# Reference table
# ---------------------------------------------------------------------------

@router.get(
    "/reference",
    response_model=list[MedicationReferenceResult],
    status_code=status.HTTP_200_OK,
    summary="Search medications reference",
)
async def search_reference(
    user_id: CurrentUser,
    search: str = Query(default="", max_length=100, description="Search term for brand or generic name"),
    service: MedicationServiceBase = Depends(get_medication_service),
) -> list[MedicationReferenceResult]:
    """Search the medications_reference table by brand or generic name.

    Returns system entries (readable by all) and the user's own created entries.
    Raises:
        HTTPException: 401 if unauthenticated.
    """
    return await service.search_reference(user_id, search)


@router.post(
    "/reference",
    response_model=MedicationReferenceResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user-defined medication reference entry",
)
async def create_reference_entry(
    payload: MedicationReferenceCreate,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> MedicationReferenceResult:
    """Create a user-scoped medications_reference entry.

    User-created entries are visible only to the creating user.
    Raises:
        HTTPException: 401 if unauthenticated.
    """
    return await service.create_reference_entry(user_id, payload)


# ---------------------------------------------------------------------------
# user_medications CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/current",
    response_model=list[MedicationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get currently active medications",
)
async def get_current_medications(
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> list[MedicationResponse]:
    """Return currently active medication stints (end_date IS NULL).

    Returns an empty list if medication tracking is disabled.
    Used by integration consumers (Ask Meno, Appointment Prep, Export).

    Raises:
        HTTPException: 401 if unauthenticated.
    """
    return await service.list_current(user_id)


@router.get(
    "",
    response_model=list[MedicationResponse],
    status_code=status.HTTP_200_OK,
    summary="List all medications (active + past)",
)
async def list_medications(
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> list[MedicationResponse]:
    """List all medication stints for the authenticated user.

    Raises:
        HTTPException: 401 if unauthenticated.
    """
    return await service.list(user_id)


@router.post(
    "",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new medication",
)
async def create_medication(
    payload: MedicationCreate,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> MedicationResponse:
    """Create a new medication stint.

    Raises:
        HTTPException: 400 if start_date is in the future.
        HTTPException: 401 if unauthenticated.
    """
    return await service.create(user_id, payload)


@router.get(
    "/{medication_id}",
    response_model=MedicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a medication stint",
)
async def get_medication(
    medication_id: str,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> MedicationResponse:
    """Get a single medication stint by ID.

    Raises:
        HTTPException: 404 if not found or not owned by user.
        HTTPException: 401 if unauthenticated.
    """
    return await service.get(user_id, medication_id)


@router.put(
    "/{medication_id}",
    response_model=MedicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a medication stint (notes / end_date only)",
)
async def update_medication(
    medication_id: str,
    payload: MedicationUpdate,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> MedicationResponse:
    """Update allowed fields on a medication stint.

    Only notes and end_date may be updated here. Dose or delivery method
    changes must use POST /medications/{id}/change (atomic dose-change flow).

    Raises:
        HTTPException: 400 if end_date < start_date.
        HTTPException: 404 if not found or not owned by user.
        HTTPException: 401 if unauthenticated.
    """
    return await service.update(user_id, medication_id, payload)


@router.post(
    "/{medication_id}/change",
    response_model=MedicationChangeDoseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Change dose or delivery method (atomic)",
)
async def change_medication_dose(
    medication_id: str,
    payload: MedicationChangeDose,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> MedicationChangeDoseResponse:
    """Atomically end the current stint and create a new one.

    The old stint's end_date is set to effective_date - 1 day. The new stint
    is created with previous_entry_id linking back. Both writes are atomic
    (Postgres RPC).

    Raises:
        HTTPException: 400 if effective_date <= start_date of old stint.
        HTTPException: 404 if medication not found, not owned by user, or already stopped.
        HTTPException: 401 if unauthenticated.
    """
    return await service.change_dose(user_id, medication_id, payload)


@router.delete(
    "/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a medication stint",
)
async def delete_medication(
    medication_id: str,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> None:
    """Delete a medication stint.

    Raises:
        HTTPException: 404 if not found or not owned by user.
        HTTPException: 401 if unauthenticated.
    """
    await service.delete(user_id, medication_id)


@router.get(
    "/{medication_id}/symptom-comparison",
    response_model=SymptomComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Before/after symptom comparison for a medication stint",
)
async def get_symptom_comparison(
    medication_id: str,
    user_id: CurrentUser,
    service: MedicationServiceBase = Depends(get_medication_service),
) -> SymptomComparisonResponse:
    """Return before/after symptom frequency data for a medication stint.

    Window length N = min(days since start_date, 90). Always returns data
    even when sparse; has_after_data=False if started today.

    Raises:
        HTTPException: 404 if medication not found or not owned by user.
        HTTPException: 401 if unauthenticated.
    """
    return await service.get_symptom_comparison(user_id, medication_id)
