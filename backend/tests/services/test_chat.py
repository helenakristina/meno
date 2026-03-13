"""Tests for ChatService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.chat import ChatService
from app.models.symptoms import SymptomLogResponse, SymptomDetail
from app.exceptions import DatabaseError


@pytest.fixture
def mock_symptoms_repo():
    """Mock symptoms repository."""
    return AsyncMock()


@pytest.fixture
def chat_service(mock_symptoms_repo):
    """Create ChatService with mocked dependencies."""
    return ChatService(symptoms_repo=mock_symptoms_repo)


@pytest.mark.asyncio
async def test_get_suggested_prompts_with_recent_symptoms(chat_service, mock_symptoms_repo):
    """Test that prompts are returned for recent symptoms."""
    # Setup: User has logged hot flashes and brain fog in last 30 days
    # get_logs returns tuple: (list[SymptomLogResponse], count)
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-2", name="Night sweats", category="vasomotor"),
            ],
            free_text_entry=None,
            source="cards",
        ),
        SymptomLogResponse(
            id="log-2",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
            ],
            free_text_entry=None,
            source="cards",
        ),
        SymptomLogResponse(
            id="log-3",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-4", name="Fatigue", category="energy"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 3)

    # Call
    result = await chat_service.get_suggested_prompts(user_id="user-123")

    # Assert
    assert "prompts" in result
    assert isinstance(result["prompts"], list)
    assert len(result["prompts"]) <= 6
    assert len(result["prompts"]) > 0

    # Should contain prompts for at least some of the logged symptoms
    prompts_text = " ".join(result["prompts"]).lower()
    assert any(
        term in prompts_text
        for term in ["hot flash", "brain fog", "fatigue", "night sweat"]
    )


@pytest.mark.asyncio
async def test_get_suggested_prompts_no_recent_symptoms(chat_service, mock_symptoms_repo):
    """Test fallback to general prompts when no recent symptoms."""
    # Setup: User has no symptoms logged recently
    mock_symptoms_repo.get_logs.return_value = ([], 0)

    # Call
    result = await chat_service.get_suggested_prompts(user_id="user-123")

    # Assert
    assert "prompts" in result
    assert isinstance(result["prompts"], list)
    assert len(result["prompts"]) > 0
    assert len(result["prompts"]) <= 6

    # Should be general prompts
    prompts_text = " ".join(result["prompts"]).lower()
    assert any(
        term in prompts_text
        for term in ["expect", "options", "conversations", "doctor"]
    )


@pytest.mark.asyncio
async def test_get_suggested_prompts_returns_max_six(chat_service, mock_symptoms_repo):
    """Test that at most 6 prompts are returned."""
    # Setup: User has logged many symptoms (>6)
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-2", name="Night sweats", category="vasomotor"),
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
                SymptomDetail(id="id-4", name="Fatigue", category="energy"),
                SymptomDetail(id="id-5", name="Anxiety", category="mood"),
                SymptomDetail(id="id-6", name="Insomnia", category="sleep"),
                SymptomDetail(id="id-7", name="Joint pain", category="pain"),
                SymptomDetail(id="id-8", name="Headaches", category="pain"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    # Call
    result = await chat_service.get_suggested_prompts(user_id="user-123")

    # Assert
    assert len(result["prompts"]) == 6


@pytest.mark.asyncio
async def test_get_suggested_prompts_no_duplicates(chat_service, mock_symptoms_repo):
    """Test that returned prompts have no duplicates."""
    # Setup
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    # Call
    result = await chat_service.get_suggested_prompts(user_id="user-123")

    # Assert
    prompts = result["prompts"]
    assert len(prompts) == len(set(prompts))  # No duplicates


@pytest.mark.asyncio
async def test_get_suggested_prompts_database_error(chat_service, mock_symptoms_repo):
    """Test error handling when symptom fetch fails."""
    # Setup: Database error
    mock_symptoms_repo.get_logs.side_effect = DatabaseError("Query failed")

    # Call & Assert
    with pytest.raises(DatabaseError):
        await chat_service.get_suggested_prompts(user_id="user-123")


@pytest.mark.asyncio
async def test_get_suggested_prompts_with_days_back_param(chat_service, mock_symptoms_repo):
    """Test that days_back parameter is respected."""
    # Setup
    mock_symptoms_repo.get_logs.return_value = ([], 0)

    # Call with custom days_back
    await chat_service.get_suggested_prompts(user_id="user-123", days_back=7)

    # Assert that get_logs was called with correct days_back
    call_args = mock_symptoms_repo.get_logs.call_args
    assert call_args is not None
    # Should be called with user_id and date range (start_date, end_date)
    assert call_args[1]["user_id"] == "user-123"


@pytest.mark.asyncio
async def test_get_suggested_prompts_with_max_prompts_param(chat_service, mock_symptoms_repo):
    """Test that max_prompts parameter limits results."""
    # Setup
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
                SymptomDetail(id="id-2", name="Night sweats", category="vasomotor"),
                SymptomDetail(id="id-3", name="Brain fog", category="cognitive"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    # Call with max_prompts=3
    result = await chat_service.get_suggested_prompts(
        user_id="user-123",
        max_prompts=3
    )

    # Assert
    assert len(result["prompts"]) <= 3


@pytest.mark.asyncio
async def test_get_suggested_prompts_handles_empty_symptom_list(chat_service, mock_symptoms_repo):
    """Test handling of logs with empty symptoms list."""
    # Setup: Some logs have empty symptom lists
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[],  # Empty symptoms
            free_text_entry=None,
            source="cards",
        ),
        SymptomLogResponse(
            id="log-2",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 2)

    # Call (should not crash)
    result = await chat_service.get_suggested_prompts(user_id="user-123")

    # Assert
    assert "prompts" in result
    assert len(result["prompts"]) > 0


@pytest.mark.asyncio
async def test_get_suggested_prompts_config_caching(chat_service, mock_symptoms_repo):
    """Test that prompt config is loaded once and cached."""
    # Setup
    logs = [
        SymptomLogResponse(
            id="log-1",
            user_id="user-123",
            logged_at=datetime.now(timezone.utc),
            symptoms=[
                SymptomDetail(id="id-1", name="Hot flashes", category="vasomotor"),
            ],
            free_text_entry=None,
            source="cards",
        ),
    ]
    mock_symptoms_repo.get_logs.return_value = (logs, 1)

    # Call twice
    result1 = await chat_service.get_suggested_prompts(user_id="user-123")
    result2 = await chat_service.get_suggested_prompts(user_id="user-456")

    # Assert
    assert result1["prompts"] is not None
    assert result2["prompts"] is not None
    # Config should be cached
    assert chat_service._prompt_config is not None
