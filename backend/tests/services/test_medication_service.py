"""Tests for MedicationService business logic."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import EntityNotFoundError, ValidationError
from app.models.medications import (
    MedicationChangeDose,
    MedicationCreate,
    MedicationResponse,
    MedicationUpdate,
)
from app.models.users import UserSettingsResponse
from app.services.medication import MedicationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = "user-1"


def make_med(
    med_id: str = "med-1",
    end_date=None,
    start_date: str = "2026-01-01",
) -> MedicationResponse:
    return MedicationResponse(
        id=med_id,
        medication_ref_id=None,
        medication_name="Estradiol",
        dose="1mg",
        delivery_method="patch",
        frequency="twice_weekly",
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date) if end_date else None,
        previous_entry_id=None,
        notes=None,
    )


def make_settings(
    mht_enabled: bool = True, journey_stage: str = "perimenopause"
) -> UserSettingsResponse:
    return UserSettingsResponse(
        period_tracking_enabled=True,
        mht_tracking_enabled=mht_enabled,
        has_uterus=True,
        journey_stage=journey_stage,
    )


def make_med_repo(
    list_all_return=None,
    list_current_return=None,
    get_return=None,
    create_return=None,
    update_return=None,
    change_dose_return="new-stint-id",
    context_return=None,
):
    from app.models.medications import MedicationContext

    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=list_all_return or [])
    repo.list_current = AsyncMock(return_value=list_current_return or [])
    repo.get = AsyncMock(return_value=get_return or make_med())
    repo.create = AsyncMock(return_value=create_return or make_med())
    repo.update = AsyncMock(return_value=update_return or make_med())
    repo.change_dose = AsyncMock(return_value=change_dose_return)
    repo.delete = AsyncMock(return_value=None)
    repo.get_context = AsyncMock(return_value=context_return or MedicationContext())
    return repo


def make_symptoms_repo():
    repo = MagicMock()
    # Returns (logs, ref_lookup) tuple as the real repo does
    repo.get_logs_with_reference = AsyncMock(return_value=([], {}))
    return repo


def make_user_repo(mht_enabled: bool = True):
    repo = MagicMock()
    repo.get_settings = AsyncMock(return_value=make_settings(mht_enabled=mht_enabled))
    return repo


def make_service(
    med_repo=None,
    mht_enabled: bool = True,
):
    return MedicationService(
        medication_repo=med_repo or make_med_repo(),
        symptoms_repo=make_symptoms_repo(),
        user_repo=make_user_repo(mht_enabled=mht_enabled),
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_success(self):
        expected = make_med()
        repo = make_med_repo(create_return=expected)
        service = make_service(med_repo=repo)
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2026, 1, 1),
        )

        result = await service.create(USER_ID, data)

        assert result.id == "med-1"
        repo.create.assert_called_once_with(USER_ID, data)

    @pytest.mark.asyncio
    async def test_create_raises_validation_error_for_future_start_date(self):
        service = make_service()
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2099, 1, 1),
        )

        with pytest.raises(ValidationError):
            await service.create(USER_ID, data)

    @pytest.mark.asyncio
    async def test_create_does_not_call_repo_on_validation_failure(self):
        repo = make_med_repo()
        service = make_service(med_repo=repo)
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2099, 1, 1),
        )

        with pytest.raises(ValidationError):
            await service.create(USER_ID, data)

        repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_success(self):
        med = make_med()
        repo = make_med_repo(get_return=med, update_return=med)
        service = make_service(med_repo=repo)
        data = MedicationUpdate(notes="updated")

        result = await service.update(USER_ID, "med-1", data)

        assert result.id == "med-1"

    @pytest.mark.asyncio
    async def test_update_raises_validation_error_when_end_date_before_start(self):
        med = make_med(start_date="2026-03-01")
        repo = make_med_repo(get_return=med)
        service = make_service(med_repo=repo)
        data = MedicationUpdate(end_date=date(2026, 2, 1))

        with pytest.raises(ValidationError):
            await service.update(USER_ID, "med-1", data)

    @pytest.mark.asyncio
    async def test_update_raises_not_found_when_repo_raises(self):
        repo = make_med_repo()
        repo.update = AsyncMock(side_effect=EntityNotFoundError("not found"))
        service = make_service(med_repo=repo)
        data = MedicationUpdate(notes="x")

        with pytest.raises(EntityNotFoundError):
            await service.update(USER_ID, "med-999", data)


# ---------------------------------------------------------------------------
# change_dose
# ---------------------------------------------------------------------------


class TestChangeDose:
    @pytest.mark.asyncio
    async def test_change_dose_returns_new_stint(self):
        med = make_med(start_date="2026-01-01")
        repo = make_med_repo(get_return=med, change_dose_return="new-id")
        service = make_service(med_repo=repo)
        data = MedicationChangeDose(
            dose="2mg",
            delivery_method="gel",
            effective_date=date(2026, 3, 1),
        )

        result = await service.change_dose(USER_ID, "med-1", data)

        assert result.new_medication_id == "new-id"

    @pytest.mark.asyncio
    async def test_change_dose_raises_validation_error_when_effective_date_not_after_start(
        self,
    ):
        med = make_med(start_date="2026-03-01")
        repo = make_med_repo(get_return=med)
        service = make_service(med_repo=repo)
        data = MedicationChangeDose(
            dose="2mg",
            delivery_method="gel",
            effective_date=date(2026, 3, 1),  # same as start — must be AFTER
        )

        with pytest.raises(ValidationError):
            await service.change_dose(USER_ID, "med-1", data)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_calls_repo_delete(self):
        repo = make_med_repo()
        service = make_service(med_repo=repo)

        await service.delete(USER_ID, "med-1")

        repo.delete.assert_called_once_with(USER_ID, "med-1")

    @pytest.mark.asyncio
    async def test_delete_propagates_not_found(self):
        repo = make_med_repo()
        repo.delete = AsyncMock(side_effect=EntityNotFoundError("not found"))
        service = make_service(med_repo=repo)

        with pytest.raises(EntityNotFoundError):
            await service.delete(USER_ID, "med-999")


# ---------------------------------------------------------------------------
# list_current — toggle gate
# ---------------------------------------------------------------------------


class TestListCurrent:
    @pytest.mark.asyncio
    async def test_list_current_returns_medications_when_enabled(self):
        meds = [make_med()]
        repo = make_med_repo(list_current_return=meds)
        service = make_service(med_repo=repo, mht_enabled=True)

        result = await service.list_current(USER_ID)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_current_returns_empty_when_mht_disabled(self):
        meds = [make_med()]
        repo = make_med_repo(list_current_return=meds)
        service = make_service(med_repo=repo, mht_enabled=False)

        result = await service.list_current(USER_ID)

        assert result == []
        repo.list_current.assert_not_called()


# ---------------------------------------------------------------------------
# get_context_if_enabled
# ---------------------------------------------------------------------------


class TestGetContextIfEnabled:
    @pytest.mark.asyncio
    async def test_returns_context_when_enabled(self):
        from app.models.medications import MedicationContext

        ctx = MedicationContext(current_medications=[make_med()])
        repo = make_med_repo(context_return=ctx)
        service = make_service(med_repo=repo, mht_enabled=True)

        result = await service.get_context_if_enabled(USER_ID)

        assert result is not None
        assert len(result.current_medications) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        from app.models.medications import MedicationContext

        ctx = MedicationContext(current_medications=[make_med()])
        repo = make_med_repo(context_return=ctx)
        service = make_service(med_repo=repo, mht_enabled=False)

        result = await service.get_context_if_enabled(USER_ID)

        assert result is None
        repo.get_context.assert_not_called()


# ---------------------------------------------------------------------------
# get_symptom_comparison
# ---------------------------------------------------------------------------


class TestGetSymptomComparison:
    @pytest.mark.asyncio
    async def test_returns_empty_comparison_when_no_logs(self):
        med = make_med(start_date="2026-01-01")
        repo = make_med_repo(get_return=med)
        symptoms_repo = make_symptoms_repo()
        service = MedicationService(
            medication_repo=repo,
            symptoms_repo=symptoms_repo,
            user_repo=make_user_repo(),
        )

        result = await service.get_symptom_comparison(USER_ID, "med-1")

        assert result.rows == []
        # No after data when logs are empty — both windows are sparse
        assert result.before_is_sparse is True
        assert result.after_is_sparse is True

    @pytest.mark.asyncio
    async def test_returns_sparse_data_flag_when_fewer_than_14_days(self):
        # Start date is recent — 7 days ago means sparse
        from datetime import timedelta

        start = (date.today() - timedelta(days=7)).isoformat()
        med = make_med(start_date=start)
        repo = make_med_repo(get_return=med)
        symptoms_repo = make_symptoms_repo()
        service = MedicationService(
            medication_repo=repo,
            symptoms_repo=symptoms_repo,
            user_repo=make_user_repo(),
        )

        result = await service.get_symptom_comparison(USER_ID, "med-1")

        assert result.after_is_sparse is True

    @pytest.mark.asyncio
    async def test_get_symptom_comparison_raises_not_found_for_wrong_med(self):
        repo = make_med_repo()
        repo.get = AsyncMock(side_effect=EntityNotFoundError("not found"))
        service = make_service(med_repo=repo)

        with pytest.raises(EntityNotFoundError):
            await service.get_symptom_comparison(USER_ID, "med-999")
