"""Tests for ExportRepository."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import DatabaseError
from app.repositories.export_repository import ExportRepository

from tests.fixtures.supabase import setup_supabase_response, setup_supabase_error


START = date(2026, 1, 1)
END = date(2026, 1, 31)
USER_ID = "user-test-123"


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def repo(mock_client):
    return ExportRepository(client=mock_client)


# ---------------------------------------------------------------------------
# record_export()
# ---------------------------------------------------------------------------


class TestRecordExport:
    @pytest.mark.asyncio
    async def test_record_export_success(self, repo, mock_client):
        inserted = {
            "id": "exp-1",
            "user_id": USER_ID,
            "export_type": "pdf",
            "date_range_start": "2026-01-01",
            "date_range_end": "2026-01-31",
        }
        setup_supabase_response(mock_client, data=[inserted])

        result = await repo.record_export(USER_ID, "pdf", START, END)

        assert result["id"] == "exp-1"
        assert result["export_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_record_export_returns_empty_dict_when_no_data(self, repo, mock_client):
        setup_supabase_response(mock_client, data=[])

        result = await repo.record_export(USER_ID, "csv", START, END)

        assert result == {}

    @pytest.mark.asyncio
    async def test_record_export_raises_database_error_on_failure(self, repo, mock_client):
        mock_client.table.return_value.insert.return_value.execute = AsyncMock(
            side_effect=Exception("DB write failed")
        )

        with pytest.raises(DatabaseError, match="Failed to record export"):
            await repo.record_export(USER_ID, "pdf", START, END)

    @pytest.mark.asyncio
    async def test_record_export_passes_correct_data(self, repo, mock_client):
        setup_supabase_response(mock_client, data=[{}])

        await repo.record_export(USER_ID, "pdf", START, END)

        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["user_id"] == USER_ID
        assert insert_call["export_type"] == "pdf"
        assert insert_call["date_range_start"] == "2026-01-01"
        assert insert_call["date_range_end"] == "2026-01-31"


# ---------------------------------------------------------------------------
# get_export_history()
# ---------------------------------------------------------------------------


class TestGetExportHistory:
    @pytest.mark.asyncio
    async def test_returns_records_and_total(self, repo, mock_client):
        records = [
            {"id": "exp-1", "export_type": "pdf"},
            {"id": "exp-2", "export_type": "csv"},
        ]
        setup_supabase_response(mock_client, data=records, count=2)

        result, total = await repo.get_export_history(USER_ID)

        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_history(self, repo, mock_client):
        setup_supabase_response(mock_client, data=[])

        result, total = await repo.get_export_history(USER_ID)

        assert result == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_raises_database_error_on_failure(self, repo, mock_client):
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.offset.return_value.execute = AsyncMock(
            side_effect=Exception("Query failed")
        )

        with pytest.raises(DatabaseError, match="Failed to get export history"):
            await repo.get_export_history(USER_ID)
