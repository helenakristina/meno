"""Abstract base class for PeriodService."""

from abc import ABC, abstractmethod
from typing import Optional

from app.models.period import (
    CreatePeriodLogResponse,
    CycleAnalysisResponse,
    PeriodLogCreate,
    PeriodLogListResponse,
    PeriodLogResponse,
    PeriodLogUpdate,
)


class PeriodServiceBase(ABC):
    """Interface contract for period tracking business logic."""

    @abstractmethod
    async def create_log(
        self, user_id: str, data: PeriodLogCreate
    ) -> CreatePeriodLogResponse: ...

    @abstractmethod
    async def get_log(self, user_id: str, log_id: str) -> PeriodLogResponse: ...

    @abstractmethod
    async def get_logs(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> PeriodLogListResponse: ...

    @abstractmethod
    async def update_log(
        self, user_id: str, log_id: str, data: PeriodLogUpdate
    ) -> PeriodLogResponse: ...

    @abstractmethod
    async def delete_log(self, user_id: str, log_id: str) -> None: ...

    @abstractmethod
    async def get_analysis(self, user_id: str) -> CycleAnalysisResponse: ...
