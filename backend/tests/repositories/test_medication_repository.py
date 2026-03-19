"""Tests for MedicationRepository — IDOR guards, CRUD, search, and RPC."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.medications import (
    MedicationChangeDose,
    MedicationCreate,
    MedicationUpdate,
)
from app.repositories.medication_repository import MedicationRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chain(data=None, error=None):
    chain = MagicMock()
    if error:
        chain.execute = AsyncMock(side_effect=error)
    else:
        chain.execute = AsyncMock(return_value=MagicMock(data=data if data is not None else []))
    for method in [
        "select", "insert", "update", "delete", "upsert",
        "eq", "neq", "gt", "gte", "lt", "lte", "is_", "not_",
        "or_", "order", "limit", "ilike",
    ]:
        getattr_mock = MagicMock(return_value=chain)
        setattr(chain, method, getattr_mock)
    # not_ needs a sub-attribute for .is_()
    chain.not_ = chain
    return chain


def make_client(chain=None):
    c = MagicMock()
    c.table.return_value = chain or make_chain()
    return c


_MED_ROW = {
    "id": "med-1",
    "medication_ref_id": None,
    "medication_name": "Estradiol",
    "dose": "1mg",
    "delivery_method": "patch",
    "frequency": "twice_weekly",
    "start_date": "2026-01-01",
    "end_date": None,
    "previous_entry_id": None,
    "notes": None,
}


# ---------------------------------------------------------------------------
# get — IDOR double-filter
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_get_applies_user_id_filter(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))

        await repo.get("owner-user", "med-1")

        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("med-1" in c for c in eq_calls), "Must filter by medication id"
        assert any("owner-user" in c for c in eq_calls), "Must filter by user_id (IDOR)"

    @pytest.mark.asyncio
    async def test_get_raises_not_found_when_no_data(self):
        chain = make_chain(data=[])
        repo = MedicationRepository(client=make_client(chain))

        with pytest.raises(EntityNotFoundError):
            await repo.get("user-1", "med-999")

    @pytest.mark.asyncio
    async def test_get_raises_database_error_on_exception(self):
        chain = make_chain(error=Exception("db down"))
        repo = MedicationRepository(client=make_client(chain))

        with pytest.raises(DatabaseError):
            await repo.get("user-1", "med-1")

    @pytest.mark.asyncio
    async def test_get_returns_medication_response(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))

        result = await repo.get("owner-user", "med-1")

        assert result.id == "med-1"
        assert result.medication_name == "Estradiol"
        assert result.delivery_method == "patch"


# ---------------------------------------------------------------------------
# update — IDOR double-filter + model_fields_set
# ---------------------------------------------------------------------------


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_applies_user_id_filter(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationUpdate(notes="updated note")

        await repo.update("owner-user", "med-1", data)

        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("med-1" in c for c in eq_calls), "Must filter by id"
        assert any("owner-user" in c for c in eq_calls), "Must filter by user_id (IDOR)"

    @pytest.mark.asyncio
    async def test_update_raises_not_found_for_wrong_user(self):
        chain = make_chain(data=[])
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationUpdate(notes="hack")

        with pytest.raises(EntityNotFoundError):
            await repo.update("attacker", "med-1", data)

    @pytest.mark.asyncio
    async def test_update_sends_only_fields_in_model_fields_set(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationUpdate(notes="only notes")

        await repo.update("owner-user", "med-1", data)

        update_payload = chain.update.call_args[0][0]
        assert "notes" in update_payload
        # end_date was NOT in model_fields_set so should not be in payload
        assert "end_date" not in update_payload

    @pytest.mark.asyncio
    async def test_update_raises_database_error_on_exception(self):
        chain = make_chain(error=Exception("fail"))
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationUpdate(notes="x")

        with pytest.raises(DatabaseError):
            await repo.update("user-1", "med-1", data)


# ---------------------------------------------------------------------------
# delete — IDOR double-filter
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_applies_user_id_filter(self):
        # First call (get) returns the row; second call (delete) also returns it
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))

        await repo.delete("owner-user", "med-1")

        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("owner-user" in c for c in eq_calls), "Must filter by user_id (IDOR)"
        assert any("med-1" in c for c in eq_calls), "Must filter by id"

    @pytest.mark.asyncio
    async def test_delete_raises_not_found_when_not_found(self):
        chain = make_chain(data=[])
        repo = MedicationRepository(client=make_client(chain))

        with pytest.raises(EntityNotFoundError):
            await repo.delete("user-1", "med-999")


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_returns_medication_response(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2026, 1, 1),
        )

        result = await repo.create("user-1", data)

        assert result.medication_name == "Estradiol"

    @pytest.mark.asyncio
    async def test_create_raises_database_error_on_exception(self):
        chain = make_chain(error=Exception("insert failed"))
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2026, 1, 1),
        )

        with pytest.raises(DatabaseError):
            await repo.create("user-1", data)

    @pytest.mark.asyncio
    async def test_create_raises_database_error_when_no_data_returned(self):
        chain = make_chain(data=[])
        repo = MedicationRepository(client=make_client(chain))
        data = MedicationCreate(
            medication_name="Estradiol",
            dose="1mg",
            delivery_method="patch",
            start_date=date(2026, 1, 1),
        )

        with pytest.raises(DatabaseError):
            await repo.create("user-1", data)


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


class TestListAll:
    @pytest.mark.asyncio
    async def test_list_all_returns_empty_list_when_no_rows(self):
        chain = make_chain(data=[])
        repo = MedicationRepository(client=make_client(chain))

        result = await repo.list_all("user-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_returns_medication_responses(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))

        result = await repo.list_all("user-1")

        assert len(result) == 1
        assert result[0].medication_name == "Estradiol"

    @pytest.mark.asyncio
    async def test_list_all_raises_database_error_on_exception(self):
        chain = make_chain(error=Exception("query failed"))
        repo = MedicationRepository(client=make_client(chain))

        with pytest.raises(DatabaseError):
            await repo.list_all("user-1")


# ---------------------------------------------------------------------------
# list_current
# ---------------------------------------------------------------------------


class TestListCurrent:
    @pytest.mark.asyncio
    async def test_list_current_returns_only_active_medications(self):
        chain = make_chain(data=[_MED_ROW])
        repo = MedicationRepository(client=make_client(chain))

        result = await repo.list_current("user-1")

        assert len(result) == 1
        assert result[0].end_date is None

    @pytest.mark.asyncio
    async def test_list_current_raises_database_error_on_exception(self):
        chain = make_chain(error=Exception("fail"))
        repo = MedicationRepository(client=make_client(chain))

        with pytest.raises(DatabaseError):
            await repo.list_current("user-1")


# ---------------------------------------------------------------------------
# change_dose — RPC
# ---------------------------------------------------------------------------


class TestChangeDose:
    @pytest.mark.asyncio
    async def test_change_dose_calls_rpc_and_returns_new_id(self):
        client = MagicMock()
        rpc_mock = MagicMock()
        rpc_mock.execute = AsyncMock(return_value=MagicMock(data="new-stint-uuid"))
        client.rpc.return_value = rpc_mock
        repo = MedicationRepository(client=client)
        data = MedicationChangeDose(
            dose="2mg",
            delivery_method="gel",
            effective_date=date(2026, 2, 1),
        )

        result = await repo.change_dose("user-1", "med-1", data, "Estradiol", None)

        assert result == "new-stint-uuid"
        client.rpc.assert_called_once_with("change_medication_dose", {
            "p_old_id": "med-1",
            "p_user_id": "user-1",
            "p_effective_date": "2026-02-01",
            "p_new_dose": "2mg",
            "p_new_delivery": "gel",
            "p_new_frequency": None,
            "p_new_notes": None,
            "p_ref_id": None,
            "p_medication_name": "Estradiol",
        })

    @pytest.mark.asyncio
    async def test_change_dose_raises_not_found_when_rpc_returns_medication_not_found(self):
        client = MagicMock()
        rpc_mock = MagicMock()
        rpc_mock.execute = AsyncMock(side_effect=Exception("medication_not_found: no rows"))
        client.rpc.return_value = rpc_mock
        repo = MedicationRepository(client=client)
        data = MedicationChangeDose(
            dose="2mg",
            delivery_method="gel",
            effective_date=date(2026, 2, 1),
        )

        with pytest.raises(EntityNotFoundError):
            await repo.change_dose("user-1", "med-1", data, "Estradiol", None)

    @pytest.mark.asyncio
    async def test_change_dose_raises_database_error_on_unexpected_exception(self):
        client = MagicMock()
        rpc_mock = MagicMock()
        rpc_mock.execute = AsyncMock(side_effect=Exception("connection reset"))
        client.rpc.return_value = rpc_mock
        repo = MedicationRepository(client=client)
        data = MedicationChangeDose(
            dose="2mg",
            delivery_method="gel",
            effective_date=date(2026, 2, 1),
        )

        with pytest.raises(DatabaseError):
            await repo.change_dose("user-1", "med-1", data, "Estradiol", None)


# ---------------------------------------------------------------------------
# search_reference
# ---------------------------------------------------------------------------


class TestSearchReference:
    @pytest.mark.asyncio
    async def test_search_reference_merges_system_and_user_results(self):
        system_row = {
            "id": "ref-1", "brand_name": "Estrogel", "generic_name": "estradiol",
            "hormone_type": "estrogen", "common_forms": ["gel"], "common_doses": ["0.75mg"],
            "notes": None, "is_user_created": False,
        }
        user_row = {
            "id": "ref-2", "brand_name": None, "generic_name": "custom estrogen",
            "hormone_type": "estrogen", "common_forms": [], "common_doses": [],
            "notes": None, "is_user_created": True,
        }
        client = MagicMock()
        chain1 = make_chain(data=[system_row])
        chain2 = make_chain(data=[user_row])
        # Two separate table() calls return different chains
        client.table.side_effect = [chain1, chain2]

        repo = MedicationRepository(client=client)
        results = await repo.search_reference("estro", "user-1")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_reference_raises_database_error_on_exception(self):
        client = MagicMock()
        chain = make_chain(error=Exception("search failed"))
        client.table.return_value = chain
        repo = MedicationRepository(client=client)

        with pytest.raises(DatabaseError):
            await repo.search_reference("estro", "user-1")
