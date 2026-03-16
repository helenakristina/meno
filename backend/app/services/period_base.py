from abc import ABC, abstractmethod

from app.models.period import (
    CycleAnalysisResponse,
    CreatePeriodLogResponse,
    PeriodLogCreate,
    PeriodLogListResponse,
    PeriodLogResponse,
    PeriodLogUpdate,
)


class PeriodServiceBase(ABC):
    @abstractmethod
    async def create_log(
        self, user_id: str, data: PeriodLogCreate
    ) -> CreatePeriodLogResponse: ...

    @abstractmethod
    async def get_logs(
        self,
        user_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> PeriodLogListResponse: ...

    @abstractmethod
    async def update_log(
        self, user_id: str, log_id: str, data: PeriodLogUpdate
    ) -> PeriodLogResponse: ...

    @abstractmethod
    async def delete_log(self, user_id: str, log_id: str) -> None: ...

    @abstractmethod
    async def get_analysis(self, user_id: str) -> CycleAnalysisResponse: ...

    @abstractmethod
    def check_postmenopausal_bleeding_alert(self, journey_stage: str | None) -> bool: ...
