"""IDOR regression tests for PeriodRepository.

Verifies that update_log and delete_log always apply the user_id ownership
filter — a future refactor that drops the .eq("user_id", ...) guard would
fail these tests before reaching production.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.period import PeriodLogUpdate
from app.repositories.period_repository import PeriodRepository


def make_chain(data=None, error=None):
    """Build a mock Supabase fluent chain."""
    chain = MagicMock()
    if error:
        chain.execute = AsyncMock(side_effect=error)
    else:
        chain.execute = AsyncMock(return_value=MagicMock(data=data or []))
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.upsert.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    return chain


def make_client(chain=None):
    client = MagicMock()
    client.table.return_value = chain or make_chain()
    return client


# ---------------------------------------------------------------------------
# IDOR: update_log must filter by both id AND user_id
# ---------------------------------------------------------------------------


class TestUpdateLogOwnership:
    @pytest.mark.asyncio
    async def test_update_log_applies_user_id_filter(self):
        """update_log must call .eq('user_id', user_id) to prevent IDOR."""
        row = {
            "id": "log-1",
            "user_id": "owner-user",
            "period_start": "2026-03-01",
            "period_end": None,
            "flow_level": "medium",
            "notes": None,
            "cycle_length": 28,
            "created_at": "2026-03-16T10:00:00+00:00",
        }
        chain = make_chain(data=[row])
        client = make_client(chain)
        repo = PeriodRepository(client=client)
        data = PeriodLogUpdate(flow_level="heavy")

        await repo.update_log("owner-user", "log-1", data)

        # Both eq filters must have been applied
        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("log-1" in c for c in eq_calls), "Must filter by log id"
        assert any("owner-user" in c for c in eq_calls), (
            "Must filter by user_id (IDOR guard)"
        )

    @pytest.mark.asyncio
    async def test_update_log_returns_not_found_for_wrong_user(self):
        """update_log returns no rows when user_id doesn't match — simulates IDOR attempt."""
        chain = make_chain(data=[])  # DB returns 0 rows (ownership filter rejected it)
        client = make_client(chain)
        repo = PeriodRepository(client=client)
        data = PeriodLogUpdate(flow_level="heavy")

        with pytest.raises(EntityNotFoundError):
            await repo.update_log("attacker-user", "log-1", data)


# ---------------------------------------------------------------------------
# IDOR: delete_log must filter by both id AND user_id
# ---------------------------------------------------------------------------


class TestDeleteLogOwnership:
    @pytest.mark.asyncio
    async def test_delete_log_applies_user_id_filter(self):
        """delete_log must call .eq('user_id', user_id) to prevent IDOR."""
        row = {"id": "log-1"}
        chain = make_chain(data=[row])
        client = make_client(chain)
        repo = PeriodRepository(client=client)

        await repo.delete_log("owner-user", "log-1")

        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("log-1" in c for c in eq_calls), "Must filter by log id"
        assert any("owner-user" in c for c in eq_calls), (
            "Must filter by user_id (IDOR guard)"
        )

    @pytest.mark.asyncio
    async def test_delete_log_returns_not_found_for_wrong_user(self):
        """delete_log returns no rows when user_id doesn't match — simulates IDOR attempt."""
        chain = make_chain(data=[])
        client = make_client(chain)
        repo = PeriodRepository(client=client)

        with pytest.raises(EntityNotFoundError):
            await repo.delete_log("attacker-user", "log-1")


# ---------------------------------------------------------------------------
# update_log: model_fields_set semantics
# ---------------------------------------------------------------------------


class TestUpdateLogModelFieldsSet:
    @pytest.mark.asyncio
    async def test_update_log_clears_notes_when_explicitly_set_to_none(self):
        """Notes can be cleared by explicitly passing null."""
        row = {
            "id": "log-1",
            "user_id": "user-1",
            "period_start": "2026-03-01",
            "period_end": None,
            "flow_level": None,
            "notes": None,
            "cycle_length": None,
            "created_at": "2026-03-16T10:00:00+00:00",
        }
        chain = make_chain(data=[row])
        client = make_client(chain)
        repo = PeriodRepository(client=client)
        # model_validate ensures "notes" is in model_fields_set even as None
        data = PeriodLogUpdate.model_validate({"notes": None, "flow_level": "light"})

        result = await repo.update_log("user-1", "log-1", data)

        assert result.notes is None

    @pytest.mark.asyncio
    async def test_update_log_skips_field_not_in_payload(self):
        """Fields not in model_fields_set must not appear in the DB update."""
        chain = make_chain(
            data=[
                {
                    "id": "log-1",
                    "user_id": "user-1",
                    "period_start": "2026-03-01",
                    "period_end": None,
                    "flow_level": "heavy",
                    "notes": "existing note",
                    "cycle_length": None,
                    "created_at": "2026-03-16T10:00:00+00:00",
                }
            ]
        )
        client = make_client(chain)
        repo = PeriodRepository(client=client)
        # Only flow_level is in model_fields_set — notes should NOT be sent to DB
        data = PeriodLogUpdate(flow_level="heavy")

        await repo.update_log("user-1", "log-1", data)

        update_call_kwargs = chain.update.call_args[0][0]
        assert "notes" not in update_call_kwargs, (
            "Should not include fields not in model_fields_set"
        )
        assert "flow_level" in update_call_kwargs
