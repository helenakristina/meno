"""Tests for PeriodService business logic."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import ValidationError
from app.models.period import (
    CycleAnalysisResponse,
    PeriodLogCreate,
    PeriodLogResponse,
    PeriodLogUpdate,
)
from app.models.users import UserSettingsResponse
from app.services.period import PeriodService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_log(
    period_start: str,
    log_id: str = "log-1",
    period_end: str | None = None,
    flow_level: str | None = None,
    cycle_length: int | None = None,
) -> PeriodLogResponse:
    return PeriodLogResponse(
        id=log_id,
        period_start=date.fromisoformat(period_start),
        period_end=date.fromisoformat(period_end) if period_end else None,
        flow_level=flow_level,
        notes=None,
        cycle_length=cycle_length,
        created_at=datetime(2026, 3, 16, tzinfo=timezone.utc),
    )


def make_repo(
    create_return=None,
    get_logs_return=None,
    get_latest_return=None,
    get_all_return=None,
    update_return=None,
    get_analysis_return=None,
):
    repo = MagicMock()
    repo.create_log = AsyncMock(return_value=create_return or make_log("2026-03-01"))
    repo.get_logs = AsyncMock(return_value=get_logs_return or [])
    repo.get_latest_log = AsyncMock(return_value=get_latest_return)
    repo.get_all_logs = AsyncMock(return_value=get_all_return or [])
    repo.update_log = AsyncMock(return_value=update_return or make_log("2026-03-01"))
    repo.delete_log = AsyncMock(return_value=None)
    repo.upsert_cycle_analysis = AsyncMock(return_value=None)
    repo.get_cycle_analysis = AsyncMock(return_value=get_analysis_return)
    return repo


def make_user_repo(journey_stage: str | None = "perimenopause"):
    user_repo = MagicMock()
    user_repo.get_settings = AsyncMock(
        return_value=UserSettingsResponse(
            period_tracking_enabled=True,
            mht_tracking_enabled=False,
            has_uterus=None,
            journey_stage=journey_stage,
        )
    )
    return user_repo


def make_service(repo=None, journey_stage: str | None = "perimenopause"):
    return PeriodService(
        period_repo=repo or make_repo(),
        user_repo=make_user_repo(journey_stage),
    )


USER_ID = "user-1"


# ---------------------------------------------------------------------------
# create_log
# ---------------------------------------------------------------------------


class TestCreateLog:
    @pytest.mark.asyncio
    async def test_create_log_success(self):
        repo = make_repo(create_return=make_log("2026-03-01"))
        service = make_service(repo)
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        result = await service.create_log(USER_ID, data)

        assert result.log.period_start == date(2026, 3, 1)
        assert result.bleeding_alert is False
        repo.create_log.assert_called_once_with(USER_ID, data)

    @pytest.mark.asyncio
    async def test_create_log_future_date_raises_validation_error(self):
        service = make_service()
        data = PeriodLogCreate(period_start=date(2099, 1, 1))

        with pytest.raises(ValidationError):
            await service.create_log(USER_ID, data)

    @pytest.mark.asyncio
    async def test_create_log_triggers_cycle_analysis_refresh(self):
        log = make_log("2026-03-01")
        repo = make_repo(create_return=log, get_all_return=[log])
        service = make_service(repo)
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        await service.create_log(USER_ID, data)

        repo.upsert_cycle_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_log_returns_bleeding_alert_for_post_menopause(self):
        repo = make_repo(create_return=make_log("2026-03-01"))
        service = make_service(repo, journey_stage="post-menopause")
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        result = await service.create_log(USER_ID, data)

        assert result.bleeding_alert is True

    @pytest.mark.asyncio
    async def test_create_log_no_bleeding_alert_for_perimenopause(self):
        repo = make_repo(create_return=make_log("2026-03-01"))
        service = make_service(repo)
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        result = await service.create_log(USER_ID, data)

        assert result.bleeding_alert is False


# ---------------------------------------------------------------------------
# get_logs
# ---------------------------------------------------------------------------


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_returns_list(self):
        logs = [make_log("2026-03-01"), make_log("2026-02-01", log_id="log-2")]
        repo = make_repo(get_logs_return=logs)
        service = make_service(repo)

        result = await service.get_logs(USER_ID)

        assert len(result.logs) == 2

    @pytest.mark.asyncio
    async def test_get_logs_passes_date_filters(self):
        repo = make_repo(get_logs_return=[])
        service = make_service(repo)

        await service.get_logs(USER_ID, start_date="2026-01-01", end_date="2026-03-31")

        repo.get_logs.assert_called_once_with(
            USER_ID, date(2026, 1, 1), date(2026, 3, 31)
        )

    @pytest.mark.asyncio
    async def test_get_logs_empty_returns_zero_total(self):
        repo = make_repo(get_logs_return=[])
        service = make_service(repo)

        result = await service.get_logs(USER_ID)

        assert result.logs == []

    @pytest.mark.asyncio
    async def test_get_logs_invalid_date_raises_validation_error(self):
        service = make_service()

        with pytest.raises(ValidationError):
            await service.get_logs(USER_ID, start_date="not-a-date")


# ---------------------------------------------------------------------------
# delete_log
# ---------------------------------------------------------------------------


class TestDeleteLog:
    @pytest.mark.asyncio
    async def test_delete_log_calls_repo_and_refreshes_analysis(self):
        repo = make_repo()
        service = make_service(repo)

        await service.delete_log(USER_ID, "log-1")

        repo.delete_log.assert_called_once_with(USER_ID, "log-1")
        repo.upsert_cycle_analysis.assert_called_once()


# ---------------------------------------------------------------------------
# get_analysis
# ---------------------------------------------------------------------------


class TestGetAnalysis:
    @pytest.mark.asyncio
    async def test_get_analysis_returns_stored_analysis(self):
        stored = CycleAnalysisResponse(
            average_cycle_length=28.0,
            cycle_variability=2.5,
            months_since_last_period=1,
            inferred_stage=None,
            has_sufficient_data=True,
        )
        logs = [
            make_log("2026-01-01", cycle_length=28),
            make_log("2026-01-29", cycle_length=28),
            make_log("2026-02-26", cycle_length=28),
        ]
        repo = make_repo(get_analysis_return=stored, get_all_return=logs)
        service = make_service(repo)

        result = await service.get_analysis(USER_ID)

        assert result.average_cycle_length == 28.0
        assert result.has_sufficient_data is True

    @pytest.mark.asyncio
    async def test_get_analysis_computes_if_not_stored(self):
        logs = [make_log("2026-01-01"), make_log("2026-01-29", cycle_length=28)]
        repo = make_repo(get_analysis_return=None, get_all_return=logs)
        service = make_service(repo)

        result = await service.get_analysis(USER_ID)

        # Should have called upsert since analysis was None
        repo.upsert_cycle_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_analysis_has_sufficient_data_when_3_plus_cycles(self):
        stored = CycleAnalysisResponse()
        logs = [
            make_log("2026-01-01", cycle_length=28),
            make_log("2026-01-29", cycle_length=28),
            make_log("2026-02-26", cycle_length=28),
            make_log("2026-03-26", cycle_length=28),  # 4th log → 3 cycle_lengths
        ]
        repo = make_repo(get_analysis_return=stored, get_all_return=logs)
        service = make_service(repo)

        result = await service.get_analysis(USER_ID)

        assert result.has_sufficient_data is True

    @pytest.mark.asyncio
    async def test_get_analysis_insufficient_data_when_fewer_than_3_cycles(self):
        stored = CycleAnalysisResponse()
        logs = [make_log("2026-01-01"), make_log("2026-01-29", cycle_length=28)]
        repo = make_repo(get_analysis_return=stored, get_all_return=logs)
        service = make_service(repo)

        result = await service.get_analysis(USER_ID)

        assert result.has_sufficient_data is False


# ---------------------------------------------------------------------------
# cycle analysis recalculation
# ---------------------------------------------------------------------------


class TestCycleAnalysisRecalculation:
    @pytest.mark.asyncio
    async def test_refresh_cycle_analysis_empty_logs(self):
        repo = make_repo(get_all_return=[])
        service = make_service(repo)

        analysis = await service._refresh_cycle_analysis(USER_ID)

        assert analysis.average_cycle_length is None
        assert analysis.has_sufficient_data is False
        repo.upsert_cycle_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_cycle_analysis_infers_menopause_at_12_months(self):
        # A log from 13 months ago triggers the inference
        from datetime import date
        today = date.today()
        old_start = today.replace(year=today.year - 2) if today.month == 1 else today.replace(
            year=today.year - 1, month=today.month - 1
        )
        log = make_log(old_start.isoformat())
        repo = make_repo(get_all_return=[log])
        service = make_service(repo)

        analysis = await service._refresh_cycle_analysis(USER_ID)

        assert analysis.inferred_stage == "menopause"

    @pytest.mark.asyncio
    async def test_refresh_cycle_analysis_no_inference_under_12_months(self):
        log = make_log(date.today().isoformat())
        repo = make_repo(get_all_return=[log])
        service = make_service(repo)

        analysis = await service._refresh_cycle_analysis(USER_ID)

        assert analysis.inferred_stage is None


# ---------------------------------------------------------------------------
# _get_journey_stage failure path
# ---------------------------------------------------------------------------


class TestGetJourneyStage:
    @pytest.mark.asyncio
    async def test_get_journey_stage_returns_none_when_user_not_found(self):
        from app.exceptions import EntityNotFoundError

        user_repo = MagicMock()
        user_repo.get_settings = AsyncMock(side_effect=EntityNotFoundError("not found"))
        repo = make_repo(create_return=make_log("2026-03-01"))
        service = PeriodService(period_repo=repo, user_repo=user_repo)
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        result = await service.create_log(USER_ID, data)

        # Falls back gracefully — no bleeding alert when stage unknown
        assert result.bleeding_alert is False

    @pytest.mark.asyncio
    async def test_get_journey_stage_returns_none_on_unexpected_exception(self):
        user_repo = MagicMock()
        user_repo.get_settings = AsyncMock(side_effect=RuntimeError("unexpected"))
        repo = make_repo(create_return=make_log("2026-03-01"))
        service = PeriodService(period_repo=repo, user_repo=user_repo)
        data = PeriodLogCreate(period_start=date(2026, 3, 1))

        result = await service.create_log(USER_ID, data)

        assert result.bleeding_alert is False
