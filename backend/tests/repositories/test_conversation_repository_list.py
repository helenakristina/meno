"""Tests for ConversationRepository.list() method."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from app.repositories.conversation_repository import ConversationRepository
from app.exceptions import DatabaseError
from tests.fixtures.supabase import setup_supabase_response


@pytest.fixture
def repository(mock_supabase):
    """Create repository with mocked client."""
    return ConversationRepository(client=mock_supabase)


class TestListConversations:
    """Test ConversationRepository.list() method."""

    @pytest.mark.asyncio
    async def test_list_returns_conversations_sorted_by_created_at_desc(
        self, repository, mock_supabase
    ):
        """Test that list returns conversations sorted by creation date (newest first)."""
        now = datetime.utcnow()
        older = (now - timedelta(days=1)).isoformat()
        newer = now.isoformat()

        rows = [
            {
                "id": "conv-1",
                "created_at": newer,
                "messages": [{"role": "user", "content": "Recent question"}],
            },
            {
                "id": "conv-2",
                "created_at": older,
                "messages": [{"role": "user", "content": "Older question"}],
            },
        ]

        setup_supabase_response(mock_supabase, data=rows, count=2)

        result_rows, total = await repository.list(
            user_id="user-123", limit=20, offset=0
        )

        assert len(result_rows) == 2
        assert total == 2
        assert result_rows[0]["created_at"] == newer
        assert result_rows[1]["created_at"] == older

    @pytest.mark.asyncio
    async def test_list_supports_pagination_with_limit_and_offset(
        self, repository, mock_supabase
    ):
        """Test pagination with limit and offset parameters."""
        rows = [
            {
                "id": "conv-3",
                "created_at": datetime.utcnow().isoformat(),
                "messages": [],
            },
        ]

        setup_supabase_response(mock_supabase, data=rows, count=100)

        result_rows, total = await repository.list(
            user_id="user-123", limit=10, offset=20
        )

        assert len(result_rows) == 1
        assert total == 100
        # Verify range was called with correct offset
        mock_supabase.table.return_value.select.return_value.order.return_value.range.assert_called_with(
            20, 29
        )

    @pytest.mark.asyncio
    async def test_list_returns_empty_for_user_with_no_conversations(
        self, repository, mock_supabase
    ):
        """Test that list returns empty list when user has no conversations."""
        setup_supabase_response(mock_supabase, data=[])
        mock_supabase.table.return_value.select.return_value.count = 0

        result_rows, total = await repository.list(
            user_id="user-no-convs", limit=20, offset=0
        )

        assert result_rows == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_raises_database_error_on_db_failure(
        self, repository, mock_supabase
    ):
        """Test that database errors are wrapped in DatabaseError (not HTTPException)."""
        # Make the execute() call raise an exception (simulating DB failure)
        mock_supabase.table.return_value.select.return_value.order.return_value.range.return_value.execute = AsyncMock(
            side_effect=ConnectionError("Connection timeout")
        )

        with pytest.raises(DatabaseError) as exc_info:
            await repository.list(user_id="user-123", limit=20, offset=0)

        assert "Failed to list conversations" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_respects_user_id_ownership(self, repository, mock_supabase):
        """Test that list query filters by user_id for ownership verification."""
        rows = [
            {
                "id": "conv-1",
                "created_at": datetime.utcnow().isoformat(),
                "messages": [],
            }
        ]

        setup_supabase_response(mock_supabase, data=rows)

        await repository.list(user_id="specific-user", limit=20, offset=0)

        # Verify eq() was called with user_id
        calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        user_id_call = [c for c in calls if "specific-user" in str(c)]
        assert len(user_id_call) > 0

    @pytest.mark.asyncio
    async def test_list_counts_messages_correctly(self, repository, mock_supabase):
        """Test that message count is accurate for conversations with multiple messages."""
        rows = [
            {
                "id": "conv-1",
                "created_at": datetime.utcnow().isoformat(),
                "messages": [
                    {"role": "user", "content": "Q1"},
                    {"role": "assistant", "content": "A1"},
                    {"role": "user", "content": "Q2"},
                    {"role": "assistant", "content": "A2"},
                ],
            }
        ]

        setup_supabase_response(mock_supabase, data=rows)

        result_rows, _ = await repository.list(user_id="user-123", limit=20, offset=0)

        assert len(result_rows[0]["messages"]) == 4

    @pytest.mark.asyncio
    async def test_list_handles_conversations_with_null_messages(
        self, repository, mock_supabase
    ):
        """Test that null/missing messages field is handled gracefully."""
        rows = [
            {
                "id": "conv-1",
                "created_at": datetime.utcnow().isoformat(),
                "messages": None,
            }
        ]

        setup_supabase_response(mock_supabase, data=rows)

        result_rows, _ = await repository.list(user_id="user-123", limit=20, offset=0)

        # Should not crash, messages should be preserved as-is for caller to handle
        assert result_rows[0]["messages"] is None
