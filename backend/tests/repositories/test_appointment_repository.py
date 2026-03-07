"""Tests for AppointmentRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.repositories.appointment_repository import AppointmentRepository
from app.models.appointment import (
    AppointmentType,
    AppointmentGoal,
    DismissalExperience,
    AppointmentContext,
    ProviderSummary,
    PersonalCheatSheet,
)
from datetime import datetime


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
        chain.order.return_value = chain
        chain.limit.return_value = chain

        return chain

    mock_client.table = MagicMock(side_effect=get_chain)
    return mock_client


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    return MagicMock()


@pytest.fixture
def repository(mock_supabase):
    """Create repository with mocked Supabase."""
    return AppointmentRepository(client=mock_supabase)


# ============================================================================
# save_context() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_context_success():
    """Test saving appointment context successfully."""
    created_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "id": created_id,
                    "user_id": "user-123",
                    "appointment_type": "new_provider",
                    "goal": "explore_hrt",
                    "dismissed_before": "once_or_twice",
                }
            ]
        )
    )
    repo = AppointmentRepository(client=mock_client)

    context = AppointmentContext(
        appointment_type=AppointmentType.new_provider,
        goal=AppointmentGoal.explore_hrt,
        dismissed_before=DismissalExperience.once_or_twice,
    )

    result = await repo.save_context("user-123", context)

    assert result == created_id


@pytest.mark.asyncio
async def test_save_context_db_error():
    """Test save_context when database insert fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().execute = AsyncMock(
        side_effect=Exception("DB connection error")
    )
    repo = AppointmentRepository(client=mock_client)

    context = AppointmentContext(
        appointment_type=AppointmentType.new_provider,
        goal=AppointmentGoal.explore_hrt,
        dismissed_before=DismissalExperience.once_or_twice,
    )

    with pytest.raises(HTTPException) as exc_info:
        await repo.save_context("user-123", context)

    assert exc_info.value.status_code == 500
    assert "Failed to create appointment context" in exc_info.value.detail


@pytest.mark.asyncio
async def test_save_context_no_data_returned():
    """Test save_context when Supabase returns empty data."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    context = AppointmentContext(
        appointment_type=AppointmentType.new_provider,
        goal=AppointmentGoal.explore_hrt,
        dismissed_before=DismissalExperience.once_or_twice,
    )

    with pytest.raises(HTTPException) as exc_info:
        await repo.save_context("user-123", context)

    assert exc_info.value.status_code == 500


# ============================================================================
# get_context() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_context_success():
    """Test fetching appointment context successfully."""
    appointment_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "id": appointment_id,
                    "user_id": "user-123",
                    "appointment_type": "new_provider",
                    "goal": "explore_hrt",
                    "dismissed_before": "once_or_twice",
                }
            ]
        )
    )
    repo = AppointmentRepository(client=mock_client)

    result = await repo.get_context(appointment_id, "user-123")

    assert isinstance(result, AppointmentContext)
    assert result.appointment_type == AppointmentType.new_provider
    assert result.goal == AppointmentGoal.explore_hrt
    assert result.dismissed_before == DismissalExperience.once_or_twice


@pytest.mark.asyncio
async def test_get_context_not_found():
    """Test get_context when context doesn't exist."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.get_context("nonexistent-id", "user-123")

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_context_db_error():
    """Test get_context when database query fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().eq().execute = AsyncMock(
        side_effect=Exception("DB connection error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.get_context("appointment-id", "user-123")

    assert exc_info.value.status_code == 500


# ============================================================================
# save_outputs() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_outputs_create_success():
    """Test creating new appointment outputs."""
    appointment_id = "550e8400-e29b-41d4-a716-446655440000"
    output_id = "660e8400-e29b-41d4-a716-446655440001"

    # First response: verify context exists
    # Second response: check if outputs exist (returns empty)
    # Third response: create new outputs
    mock_client = make_sequential_client(
        MagicMock(data=[{"id": appointment_id}]),  # Context exists
        MagicMock(data=[]),  # No existing outputs
        MagicMock(
            data=[
                {
                    "id": output_id,
                    "user_id": "user-123",
                    "context_id": appointment_id,
                    "provider_summary_content": "Summary",
                }
            ]
        ),
    )
    repo = AppointmentRepository(client=mock_client)

    provider_summary = ProviderSummary(
        content="Summary of symptoms",
        generated_at=datetime.now(),
    )

    result = await repo.save_outputs(appointment_id, "user-123", provider_summary=provider_summary)

    assert result == output_id


@pytest.mark.asyncio
async def test_save_outputs_context_not_found():
    """Test save_outputs when context doesn't exist."""
    mock_client = make_sequential_client(MagicMock(data=[]))  # Context not found
    repo = AppointmentRepository(client=mock_client)

    provider_summary = ProviderSummary(
        content="Summary",
        generated_at=datetime.now(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await repo.save_outputs("nonexistent-id", "user-123", provider_summary=provider_summary)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_save_outputs_context_verification_error():
    """Test save_outputs when context verification fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().eq().execute = AsyncMock(
        side_effect=Exception("DB error")
    )
    repo = AppointmentRepository(client=mock_client)

    provider_summary = ProviderSummary(
        content="Summary",
        generated_at=datetime.now(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await repo.save_outputs("appointment-id", "user-123", provider_summary=provider_summary)

    assert exc_info.value.status_code == 500


# ============================================================================
# get_latest() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_latest_success():
    """Test fetching the latest appointment prep outputs."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "id": "output-id",
                    "user_id": "user-123",
                    "context_id": "context-id",
                    "narrative": "Symptom summary",
                    "concerns": ["fatigue", "brain fog"],
                    "provider_summary_content": "Provider summary",
                    "personal_cheat_sheet_content": "Cheat sheet",
                    "created_at": "2026-03-05T10:00:00Z",
                }
            ]
        )
    )
    repo = AppointmentRepository(client=mock_client)

    result = await repo.get_latest("user-123")

    assert result is not None
    assert result["id"] == "output-id"
    assert result["narrative"] == "Symptom summary"


@pytest.mark.asyncio
async def test_get_latest_not_found():
    """Test get_latest when user has no appointment preps."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    result = await repo.get_latest("user-with-no-preps")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_db_error():
    """Test get_latest when database query fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().order().limit().execute = AsyncMock(
        side_effect=Exception("DB connection error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.get_latest("user-123")

    assert exc_info.value.status_code == 500
