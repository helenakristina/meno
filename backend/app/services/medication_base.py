"""Abstract base class for MedicationService."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.models.medications import (
    MedicationChangeDose,
    MedicationChangeDoseResponse,
    MedicationContext,
    MedicationCreate,
    MedicationReferenceCreate,
    MedicationReferenceResult,
    MedicationResponse,
    MedicationUpdate,
    SymptomComparisonResponse,
)


class MedicationServiceBase(ABC):
    """Interface contract for MHT medication tracking business logic."""

    @abstractmethod
    async def search_reference(
        self, user_id: str, query: str
    ) -> list[MedicationReferenceResult]: ...

    @abstractmethod
    async def create_reference_entry(
        self, user_id: str, data: MedicationReferenceCreate
    ) -> MedicationReferenceResult: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[MedicationResponse]: ...

    @abstractmethod
    async def list_current(self, user_id: str) -> list[MedicationResponse]: ...

    @abstractmethod
    async def get(self, user_id: str, medication_id: str) -> MedicationResponse: ...

    @abstractmethod
    async def create(
        self, user_id: str, data: MedicationCreate
    ) -> MedicationResponse: ...

    @abstractmethod
    async def update(
        self, user_id: str, medication_id: str, data: MedicationUpdate
    ) -> MedicationResponse: ...

    @abstractmethod
    async def change_dose(
        self, user_id: str, medication_id: str, data: MedicationChangeDose
    ) -> MedicationChangeDoseResponse: ...

    @abstractmethod
    async def delete(self, user_id: str, medication_id: str) -> None: ...

    @abstractmethod
    async def get_symptom_comparison(
        self, user_id: str, medication_id: str
    ) -> SymptomComparisonResponse: ...

    @abstractmethod
    async def get_context_if_enabled(self, user_id: str) -> MedicationContext | None: ...

    @abstractmethod
    async def list_active_during(
        self, user_id: str, range_start: date, range_end: date
    ) -> list[MedicationResponse]: ...
