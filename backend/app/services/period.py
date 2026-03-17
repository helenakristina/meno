"""Business logic for period tracking and cycle analysis."""

import logging
from datetime import date
from typing import Optional

from app.exceptions import EntityNotFoundError, ValidationError
from app.models.period import (
    CycleAnalysisResponse,
    CreatePeriodLogResponse,
    PeriodLogCreate,
    PeriodLogListResponse,
    PeriodLogResponse,
    PeriodLogUpdate,
)
from app.repositories.period_repository import PeriodRepository
from app.repositories.user_repository import UserRepository
from app.services.period_base import PeriodServiceBase
from app.utils.dates import (
    calculate_cycle_variability,
    months_since_date,
)
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

# Minimum cycle count to consider analysis statistically meaningful
MIN_CYCLES_FOR_ANALYSIS = 3


class PeriodService(PeriodServiceBase):
    """Handles period log CRUD and cycle analysis calculations."""

    def __init__(self, period_repo: PeriodRepository, user_repo: UserRepository):
        self.period_repo = period_repo
        self.user_repo = user_repo

    async def create_log(
        self, user_id: str, data: PeriodLogCreate
    ) -> CreatePeriodLogResponse:
        """Create a period log and refresh cycle analysis.

        Args:
            user_id: Authenticated user ID.
            data: Period log data.

        Returns:
            CreatePeriodLogResponse with the log and bleeding_alert flag.

        Raises:
            ValidationError: If period_start is in the future.
        """
        if data.period_start > date.today():
            raise ValidationError("period_start cannot be in the future")

        log = await self.period_repo.create_log(user_id, data)
        logger.info("Period log created for user=%s", hash_user_id(user_id))

        # Refresh cycle analysis after every create
        await self._refresh_cycle_analysis(user_id)

        journey_stage = await self._get_journey_stage(user_id)
        bleeding_alert = journey_stage == "post-menopause"

        return CreatePeriodLogResponse(log=log, bleeding_alert=bleeding_alert)

    async def get_log(self, user_id: str, log_id: str) -> PeriodLogResponse:
        """Fetch a single period log by ID.

        Args:
            user_id: Authenticated user ID.
            log_id: ID of the log to fetch.

        Returns:
            PeriodLogResponse.
        """
        return await self.period_repo.get_log(user_id, log_id)

    async def get_logs(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> PeriodLogListResponse:
        """Fetch period logs with optional date filtering.

        Args:
            user_id: Authenticated user ID.
            start_date: ISO date string for range start (inclusive).
            end_date: ISO date string for range end (inclusive).

        Returns:
            PeriodLogListResponse.
        """
        try:
            start = date.fromisoformat(start_date) if start_date else None
            end = date.fromisoformat(end_date) if end_date else None
        except ValueError as exc:
            raise ValidationError(f"Invalid date format: {exc}") from exc

        logs = await self.period_repo.get_logs(user_id, start, end)
        return PeriodLogListResponse(logs=logs)

    async def update_log(
        self, user_id: str, log_id: str, data: PeriodLogUpdate
    ) -> PeriodLogResponse:
        """Update a period log.

        Args:
            user_id: Authenticated user ID.
            log_id: ID of the log to update.
            data: Fields to update.

        Returns:
            Updated PeriodLogResponse.
        """
        return await self.period_repo.update_log(user_id, log_id, data)

    async def delete_log(self, user_id: str, log_id: str) -> None:
        """Delete a period log and refresh cycle analysis.

        Args:
            user_id: Authenticated user ID.
            log_id: ID of the log to delete.
        """
        await self.period_repo.delete_log(user_id, log_id)
        logger.info("Period log deleted for user=%s", hash_user_id(user_id))

        # Refresh cycle analysis after deletion (previous log becomes latest)
        await self._refresh_cycle_analysis(user_id)

    async def get_analysis(self, user_id: str) -> CycleAnalysisResponse:
        """Get cycle analysis, computing it fresh if needed.

        Args:
            user_id: Authenticated user ID.

        Returns:
            CycleAnalysisResponse with has_sufficient_data flag.
        """
        analysis = await self.period_repo.get_cycle_analysis(user_id)
        if analysis is None:
            # No analysis stored yet — compute it now (has_sufficient_data set inside)
            return await self._refresh_cycle_analysis(user_id)

        # Recompute has_sufficient_data for cached analysis (not persisted)
        all_logs = await self.period_repo.get_all_logs(user_id)
        cycle_lengths = [log.cycle_length for log in all_logs if log.cycle_length is not None]
        analysis.has_sufficient_data = len(cycle_lengths) >= MIN_CYCLES_FOR_ANALYSIS

        return analysis

    async def _refresh_cycle_analysis(self, user_id: str) -> CycleAnalysisResponse:
        """Recompute cycle analysis from all period logs and persist it.

        Args:
            user_id: ID of the user.

        Returns:
            Updated CycleAnalysisResponse.
        """
        all_logs = await self.period_repo.get_all_logs(user_id)

        if not all_logs:
            empty = CycleAnalysisResponse(has_sufficient_data=False)
            await self.period_repo.upsert_cycle_analysis(user_id, empty)
            return empty

        # Calculate cycle lengths (skip logs with no cycle_length, but also recompute
        # from the ordered sequence to ensure accuracy after deletions)
        cycle_lengths: list[int] = []
        for i in range(1, len(all_logs)):
            delta = (all_logs[i].period_start - all_logs[i - 1].period_start).days
            if delta > 0:
                cycle_lengths.append(delta)

        avg = sum(cycle_lengths) / len(cycle_lengths) if cycle_lengths else None
        variability = calculate_cycle_variability(cycle_lengths) if cycle_lengths else None

        latest = all_logs[-1]  # most recent (ascending order)
        months_since = max(0, months_since_date(latest.period_start))

        # Infer stage: 12+ months since last period → menopause milestone
        inferred_stage = None
        if months_since >= 12:
            inferred_stage = "menopause"

        analysis = CycleAnalysisResponse(
            average_cycle_length=avg,
            cycle_variability=variability,
            months_since_last_period=months_since,
            inferred_stage=inferred_stage,
            has_sufficient_data=len(cycle_lengths) >= MIN_CYCLES_FOR_ANALYSIS,
        )

        await self.period_repo.upsert_cycle_analysis(user_id, analysis)
        return analysis

    async def _get_journey_stage(self, user_id: str) -> Optional[str]:
        """Fetch user's journey stage via UserRepository.

        Falls back to None gracefully if the user is not found.
        """
        try:
            settings = await self.user_repo.get_settings(user_id)
            return settings.journey_stage
        except EntityNotFoundError:
            return None
        except Exception as exc:
            logger.warning("Failed to fetch journey stage for user=%s: %s", hash_user_id(user_id), exc)
            return None
