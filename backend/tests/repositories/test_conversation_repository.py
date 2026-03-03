"""Tests for ConversationRepository."""

import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.repositories.conversation_repository import ConversationRepository


def make_sequential_client(*responses):
    """Create a mock Supabase client that handles sequential method chains.

    Each response is used for one complete chain (table().select().eq().execute()).
    """
    mock_client = MagicMock()
    response_iter = iter(responses)

    def get_chain(*args, **kwargs):
        try:
            response_data = next(response_iter)
        except StopIteration:
            response_data = MagicMock()

        # Set up the chain
        chain = MagicMock()
        chain.execute = AsyncMock(return_value=response_data)

        # Make all intermediate methods return objects that support further chaining
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.update.return_value = chain
        chain.insert.return_value = chain
        chain.delete.return_value = chain

        return chain

    mock_client.table = MagicMock(side_effect=get_chain)
    return mock_client


# ---------------------------------------------------------------------------
# load() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_conversation_success():
    """Test loading messages from an existing conversation."""
    conversation_id = uuid4()
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    mock_client = make_sequential_client(
        MagicMock(data=[{"messages": messages}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.load(conversation_id, "user-1")

    assert result == messages


@pytest.mark.asyncio
async def test_load_conversation_empty_messages():
    """Test loading a conversation with empty messages array."""
    conversation_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[{"messages": []}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.load(conversation_id, "user-1")

    assert result == []


@pytest.mark.asyncio
async def test_load_conversation_null_messages():
    """Test loading a conversation with null messages field."""
    conversation_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[{"messages": None}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.load(conversation_id, "user-1")

    assert result == []


@pytest.mark.asyncio
async def test_load_conversation_not_found():
    """Test that loading non-existent conversation raises 404."""
    conversation_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[])
    )
    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.load(conversation_id, "user-1")

    assert exc_info.value.status_code == 404
    assert "Conversation not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_load_conversation_db_error():
    """Test that database errors raise 500."""
    conversation_id = uuid4()

    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    mock_client.table.return_value = chain

    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.load(conversation_id, "user-1")

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# save() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_conversation_update_existing():
    """Test updating an existing conversation."""
    conversation_id = uuid4()
    messages = [
        {"role": "user", "content": "Updated message"},
    ]

    mock_client = make_sequential_client(
        MagicMock(data=[{"id": str(conversation_id)}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.save(conversation_id, "user-1", messages)

    assert result == conversation_id


@pytest.mark.asyncio
async def test_save_conversation_create_new():
    """Test creating a new conversation."""
    new_id = uuid4()
    messages = [
        {"role": "user", "content": "First message"},
        {"role": "assistant", "content": "First response"},
    ]

    mock_client = make_sequential_client(
        MagicMock(data=[{"id": str(new_id)}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.save(None, "user-1", messages)

    assert result == new_id


@pytest.mark.asyncio
async def test_save_conversation_create_empty_messages():
    """Test creating a new conversation with empty messages."""
    new_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[{"id": str(new_id)}])
    )
    repo = ConversationRepository(client=mock_client)

    result = await repo.save(None, "user-1", [])

    assert result == new_id


@pytest.mark.asyncio
async def test_save_conversation_update_fails():
    """Test that update errors raise 500."""
    conversation_id = uuid4()

    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB error"))
    chain.eq.return_value = chain
    chain.update.return_value = chain
    mock_client.table.return_value = chain

    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.save(conversation_id, "user-1", [{"role": "user", "content": "test"}])

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_save_conversation_create_fails():
    """Test that insert errors raise 500."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB error"))
    chain.insert.return_value = chain
    mock_client.table.return_value = chain

    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.save(None, "user-1", [])

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_save_conversation_create_returns_empty():
    """Test that empty insert response raises 500."""
    mock_client = make_sequential_client(
        MagicMock(data=[])
    )
    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.save(None, "user-1", [])

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# delete() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_conversation_success():
    """Test deleting an existing conversation."""
    conversation_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[{"id": str(conversation_id)}])
    )
    repo = ConversationRepository(client=mock_client)

    await repo.delete(conversation_id, "user-1")
    # No assertion needed; should not raise


@pytest.mark.asyncio
async def test_delete_conversation_not_found():
    """Test that deleting non-existent conversation raises 404."""
    conversation_id = uuid4()

    mock_client = make_sequential_client(
        MagicMock(data=[])
    )
    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.delete(conversation_id, "user-1")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_db_error():
    """Test that database errors raise 500."""
    conversation_id = uuid4()

    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB error"))
    chain.eq.return_value = chain
    chain.delete.return_value = chain
    mock_client.table.return_value = chain

    repo = ConversationRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.delete(conversation_id, "user-1")

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conversation_workflow():
    """Test complete workflow: create, load, update, delete."""
    user_id = "user-1"
    new_id = uuid4()

    # Create conversation
    mock_create = make_sequential_client(
        MagicMock(data=[{"id": str(new_id)}])
    )
    repo = ConversationRepository(client=mock_create)

    created_id = await repo.save(None, user_id, [])
    assert created_id == new_id

    # Load conversation
    messages = [{"role": "user", "content": "test"}]
    mock_load = make_sequential_client(
        MagicMock(data=[{"messages": messages}])
    )
    repo = ConversationRepository(client=mock_load)

    loaded_messages = await repo.load(new_id, user_id)
    assert loaded_messages == messages

    # Update conversation
    updated_messages = [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "response"},
    ]
    mock_update = make_sequential_client(
        MagicMock(data=[{"id": str(new_id)}])
    )
    repo = ConversationRepository(client=mock_update)

    updated_id = await repo.save(new_id, user_id, updated_messages)
    assert updated_id == new_id

    # Delete conversation
    mock_delete = make_sequential_client(
        MagicMock(data=[{"id": str(new_id)}])
    )
    repo = ConversationRepository(client=mock_delete)

    await repo.delete(new_id, user_id)
    # Should not raise
