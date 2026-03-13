"""Tests for AppointmentRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import DatabaseError, EntityNotFoundError
from app.repositories.appointment_repository import AppointmentRepository
from app.models.appointment import (
    AppointmentType,
    AppointmentGoal,
    DismissalExperience,
    AppointmentContext,
    ProviderSummary,
    PersonalCheatSheet,
)
from datetime import datetime, timezone


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
async def test_save_context_with_urgent_symptom():
    """Test saving appointment context with urgent_symptom when goal is urgent_symptom."""
    created_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "id": created_id,
                    "user_id": "user-123",
                    "appointment_type": "new_provider",
                    "goal": "urgent_symptom",
                    "dismissed_before": "once_or_twice",
                    "urgent_symptom": "hot flashes",
                }
            ]
        )
    )
    repo = AppointmentRepository(client=mock_client)

    context = AppointmentContext(
        appointment_type=AppointmentType.new_provider,
        goal=AppointmentGoal.urgent_symptom,
        dismissed_before=DismissalExperience.once_or_twice,
        urgent_symptom="hot flashes",
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

    with pytest.raises(DatabaseError) as exc_info:
        await repo.save_context("user-123", context)

    assert "Failed to create appointment context" in str(exc_info.value)


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

    with pytest.raises(DatabaseError):
        await repo.save_context("user-123", context)


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
async def test_get_context_with_urgent_symptom():
    """Test fetching appointment context with urgent_symptom."""
    appointment_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "id": appointment_id,
                    "user_id": "user-123",
                    "appointment_type": "new_provider",
                    "goal": "urgent_symptom",
                    "dismissed_before": "once_or_twice",
                    "urgent_symptom": "sleep disruption",
                }
            ]
        )
    )
    repo = AppointmentRepository(client=mock_client)

    result = await repo.get_context(appointment_id, "user-123")

    assert isinstance(result, AppointmentContext)
    assert result.appointment_type == AppointmentType.new_provider
    assert result.goal == AppointmentGoal.urgent_symptom
    assert result.dismissed_before == DismissalExperience.once_or_twice
    assert result.urgent_symptom == "sleep disruption"


@pytest.mark.asyncio
async def test_get_context_not_found():
    """Test get_context when context doesn't exist."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.get_context("nonexistent-id", "user-123")

    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_context_db_error():
    """Test get_context when database query fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().eq().execute = AsyncMock(
        side_effect=Exception("DB connection error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_context("appointment-id", "user-123")


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

    with pytest.raises(EntityNotFoundError):
        await repo.save_outputs("nonexistent-id", "user-123", provider_summary=provider_summary)


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

    with pytest.raises(DatabaseError):
        await repo.save_outputs("appointment-id", "user-123", provider_summary=provider_summary)


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

    with pytest.raises(DatabaseError):
        await repo.get_latest("user-123")


# ============================================================================
# save_narrative() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_narrative_success():
    """Test saving appointment narrative successfully."""
    appointment_id = "appt-123"
    user_id = "user-456"
    narrative_text = "This is the generated narrative summary."

    # Mock successful update response
    update_response = MagicMock(data=[{"id": appointment_id}])
    mock_client = make_sequential_client(update_response)
    repo = AppointmentRepository(client=mock_client)

    # Should complete without error (returns None)
    await repo.save_narrative(appointment_id, user_id, narrative_text)
    # No assertion needed, just verifying no exception


@pytest.mark.asyncio
async def test_save_narrative_not_found():
    """Test save_narrative when context doesn't exist."""
    mock_client = make_sequential_client(MagicMock(data=[]))  # No rows updated
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.save_narrative("appt-123", "user-456", "narrative text")

    assert "Appointment context not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_save_narrative_db_error():
    """Test save_narrative when database update fails."""
    mock_client = MagicMock()
    mock_client.table().update().eq().eq().execute = AsyncMock(
        side_effect=Exception("DB error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.save_narrative("appt-123", "user-456", "narrative")


# ============================================================================
# save_concerns() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_concerns_success():
    """Test saving prioritized concerns successfully."""
    appointment_id = "appt-123"
    user_id = "user-456"
    concerns = ["Hot flashes affecting work", "Sleep disruption"]

    update_response = MagicMock(data=[{"id": appointment_id}])
    mock_client = make_sequential_client(update_response)
    repo = AppointmentRepository(client=mock_client)

    # Should complete without error
    await repo.save_concerns(appointment_id, user_id, concerns)


@pytest.mark.asyncio
async def test_save_concerns_not_found():
    """Test save_concerns when context doesn't exist."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError):
        await repo.save_concerns("appt-123", "user-456", [])


# ============================================================================
# save_scenarios() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_scenarios_success():
    """Test saving scenario cards successfully."""
    appointment_id = "appt-123"
    user_id = "user-456"
    scenarios = [
        {"id": "s1", "title": "Best case", "situation": "Best outcome", "suggestion": "Discuss options", "category": "positive"},
        {"id": "s2", "title": "Worst case", "situation": "Worst outcome", "suggestion": "Know alternatives", "category": "negative"},
    ]

    update_response = MagicMock(data=[{"id": appointment_id}])
    mock_client = make_sequential_client(update_response)
    repo = AppointmentRepository(client=mock_client)

    # Should complete without error
    await repo.save_scenarios(appointment_id, user_id, scenarios)


@pytest.mark.asyncio
async def test_save_scenarios_db_error():
    """Test save_scenarios when database update fails."""
    mock_client = MagicMock()
    mock_client.table().update().eq().eq().execute = AsyncMock(
        side_effect=Exception("DB error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.save_scenarios("appt-123", "user-456", [])


# ============================================================================
# save_pdf_metadata() tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_pdf_metadata_success():
    """Test saving PDF metadata successfully."""
    user_id = "user-456"
    appointment_id = "appt-123"
    provider_path = "user-456/appt-123/provider.pdf"
    cheatsheet_path = "user-456/appt-123/cheatsheet.pdf"

    pdf_response = MagicMock(data=[{"id": "metadata-789"}])
    mock_client = make_sequential_client(pdf_response)
    repo = AppointmentRepository(client=mock_client)

    result = await repo.save_pdf_metadata(user_id, appointment_id, provider_path, cheatsheet_path)

    assert result == "metadata-789"


@pytest.mark.asyncio
async def test_save_pdf_metadata_no_data_returned():
    """Test save_pdf_metadata when database returns no data."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.save_pdf_metadata("user-456", "appt-123", "path1", "path2")


# ============================================================================
# get_user_prep_history() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_user_prep_history_success():
    """Test fetching user's appointment prep history."""
    # Set up mock client with two table calls
    mock_client = MagicMock()

    # First table() call: count query
    count_chain = MagicMock()
    count_chain.select.return_value = count_chain
    count_chain.eq.return_value = count_chain
    count_response = MagicMock(count=2)
    count_chain.execute = AsyncMock(return_value=count_response)

    # Second table() call: data query with range
    data_chain = MagicMock()
    data_chain.select.return_value = data_chain
    data_chain.eq.return_value = data_chain
    data_chain.order.return_value = data_chain
    data_chain.range.return_value = data_chain
    data_response = MagicMock(
        data=[
            {"id": "metadata-1", "appointment_id": "appt-1", "generated_at": "2026-03-05T14:00:00Z"},
            {"id": "metadata-2", "appointment_id": "appt-2", "generated_at": "2026-03-01T10:00:00Z"},
        ]
    )
    data_chain.execute = AsyncMock(return_value=data_response)

    # Make table() alternate between count and data chains
    call_count = [0]
    def table_side_effect(*args, **kwargs):
        call_count[0] += 1
        return count_chain if call_count[0] == 1 else data_chain

    mock_client.table.side_effect = table_side_effect
    repo = AppointmentRepository(client=mock_client)

    preps, total = await repo.get_user_prep_history("user-123")

    assert len(preps) == 2
    assert total == 2
    assert preps[0]["id"] == "metadata-1"


@pytest.mark.asyncio
async def test_get_user_prep_history_empty():
    """Test get_user_prep_history when user has no appointment preps."""
    mock_client = MagicMock()

    # Count query
    count_chain = MagicMock()
    count_chain.select.return_value = count_chain
    count_chain.eq.return_value = count_chain
    count_response = MagicMock(count=0)
    count_chain.execute = AsyncMock(return_value=count_response)

    # Data query
    data_chain = MagicMock()
    data_chain.select.return_value = data_chain
    data_chain.eq.return_value = data_chain
    data_chain.order.return_value = data_chain
    data_chain.range.return_value = data_chain
    data_chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    call_count = [0]
    def table_side_effect(*args, **kwargs):
        call_count[0] += 1
        return count_chain if call_count[0] == 1 else data_chain

    mock_client.table.side_effect = table_side_effect
    repo = AppointmentRepository(client=mock_client)

    preps, total = await repo.get_user_prep_history("user-123")

    assert preps == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_user_prep_history_db_error():
    """Test get_user_prep_history when database query fails."""
    mock_client = MagicMock()
    mock_client.table().select().eq().order().range().execute = AsyncMock(
        side_effect=Exception("DB connection error")
    )
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_user_prep_history("user-123")


# ============================================================================
# save_outputs() additional tests for uncovered paths
# ============================================================================


@pytest.mark.asyncio
async def test_save_outputs_update_existing():
    """Test save_outputs when outputs already exist (update path)."""
    appointment_id = "appt-123"
    user_id = "user-456"
    output_id = "output-789"

    # Verify context exists
    context_response = MagicMock(data=[{"id": appointment_id}])

    # Check for existing outputs (found)
    existing_response = MagicMock(data=[{"id": output_id}])

    # Update succeeds
    update_response = MagicMock(data=[{"id": output_id}])

    mock_client = make_sequential_client(
        context_response, existing_response, update_response
    )
    repo = AppointmentRepository(client=mock_client)

    provider_summary = ProviderSummary(
        content="Provider summary text",
        generated_at=datetime.now(timezone.utc),
    )

    result = await repo.save_outputs(appointment_id, user_id, provider_summary=provider_summary)

    assert result == output_id


@pytest.mark.asyncio
async def test_save_outputs_with_both_summaries():
    """Test save_outputs with both provider summary and personal cheat sheet."""
    appointment_id = "appt-123"
    user_id = "user-456"

    context_response = MagicMock(data=[{"id": appointment_id}])
    existing_response = MagicMock(data=[])  # No existing outputs
    new_output_response = MagicMock(data=[{"id": "new-output-789"}])

    mock_client = make_sequential_client(
        context_response, existing_response, new_output_response
    )
    repo = AppointmentRepository(client=mock_client)

    provider_summary = ProviderSummary(
        content="Provider info",
        generated_at=datetime.now(timezone.utc),
    )
    personal_sheet = PersonalCheatSheet(
        content="Personal notes",
        generated_at=datetime.now(timezone.utc),
    )

    result = await repo.save_outputs(
        appointment_id,
        user_id,
        provider_summary=provider_summary,
        personal_cheat_sheet=personal_sheet,
    )

    assert result == "new-output-789"


@pytest.mark.asyncio
async def test_save_outputs_existing_check_error():
    """Test save_outputs when checking for existing outputs fails."""
    mock_client = MagicMock()

    # Verify context succeeds
    context_chain = MagicMock()
    context_chain.select.return_value = context_chain
    context_chain.eq.return_value = context_chain
    context_chain.execute = AsyncMock(return_value=MagicMock(data=[{"id": "appt"}]))

    # Check for existing fails
    existing_chain = MagicMock()
    existing_chain.select.return_value = existing_chain
    existing_chain.eq.return_value = existing_chain
    existing_chain.execute = AsyncMock(side_effect=Exception("Query failed"))

    call_count = [0]
    def table_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return context_chain
        return existing_chain

    mock_client.table.side_effect = table_side_effect
    repo = AppointmentRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.save_outputs("appt-123", "user-456", provider_summary=None)
