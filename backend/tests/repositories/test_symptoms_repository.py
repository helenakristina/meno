"""Tests for SymptomsRepository."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.exceptions import DatabaseError, ValidationError

from app.repositories.symptoms_repository import SymptomsRepository
from app.models.symptoms import SymptomDetail


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
        chain.gte.return_value = chain
        chain.lte.return_value = chain
        chain.in_.return_value = chain

        return chain

    mock_client.table = MagicMock(side_effect=get_chain)
    return mock_client


# ---------------------------------------------------------------------------
# validate_ids() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_ids_empty_list():
    """Test that empty symptom ID list passes validation."""
    mock_client = make_sequential_client()
    repo = SymptomsRepository(client=mock_client)

    await repo.validate_ids([])


@pytest.mark.asyncio
async def test_validate_ids_success():
    """Test validating existing symptom IDs."""
    mock_client = make_sequential_client(
        MagicMock(data=[{"id": "symptom-1"}, {"id": "symptom-2"}])
    )
    repo = SymptomsRepository(client=mock_client)

    await repo.validate_ids(["symptom-1", "symptom-2"])


@pytest.mark.asyncio
async def test_validate_ids_with_duplicates():
    """Test that duplicate IDs in request are deduplicated before validation."""
    mock_client = make_sequential_client(MagicMock(data=[{"id": "symptom-1"}]))
    repo = SymptomsRepository(client=mock_client)

    await repo.validate_ids(["symptom-1", "symptom-1", "symptom-1"])


@pytest.mark.asyncio
async def test_validate_ids_invalid():
    """Test that invalid symptom IDs raise 400."""
    mock_client = make_sequential_client(
        MagicMock(data=[{"id": "symptom-1"}])  # Only 1 of 2 exists
    )
    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(ValidationError) as exc_info:
        await repo.validate_ids(["symptom-1", "symptom-999"])

    assert "Invalid symptom IDs" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_ids_db_error():
    """Test that DB errors raise 500."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.in_.return_value = chain
    mock_client.table.return_value = chain

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.validate_ids(["symptom-1"])


# ---------------------------------------------------------------------------
# get_summary() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_summary_found():
    """Test fetching existing symptom summary."""
    mock_client = make_sequential_client(
        MagicMock(data=[{"summary_text": "Fatigue on 5 days"}])
    )
    repo = SymptomsRepository(client=mock_client)

    result = await repo.get_summary("user-1")

    assert result == "Fatigue on 5 days"


@pytest.mark.asyncio
async def test_get_summary_not_found():
    """Test that missing summary returns default message."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = SymptomsRepository(client=mock_client)

    result = await repo.get_summary("user-1")

    assert result == "No symptom data logged yet."


@pytest.mark.asyncio
async def test_get_summary_null_text():
    """Test that null summary_text returns default message."""
    mock_client = make_sequential_client(MagicMock(data=[{"summary_text": None}]))
    repo = SymptomsRepository(client=mock_client)

    result = await repo.get_summary("user-1")

    assert result == "No symptom data logged yet."


@pytest.mark.asyncio
async def test_get_summary_db_error_returns_default():
    """Test that DB errors gracefully return default message."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB error"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    mock_client.table.return_value = chain

    repo = SymptomsRepository(client=mock_client)
    result = await repo.get_summary("user-1")

    assert result == "No symptom data logged yet."


# ---------------------------------------------------------------------------
# create_log() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_log_success():
    """Test creating a symptom log successfully."""
    logged_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_client = make_sequential_client(
        # validate_ids response
        MagicMock(data=[{"id": "symptom-1"}, {"id": "symptom-2"}]),
        # insert response
        MagicMock(
            data=[
                {
                    "id": "log-123",
                    "user_id": "user-1",
                    "logged_at": logged_at,
                    "symptoms": ["symptom-1", "symptom-2"],
                    "free_text_entry": "Tired",
                    "source": "cards",
                }
            ]
        ),
        # lookup response
        MagicMock(
            data=[
                {"id": "symptom-1", "name": "Fatigue", "category": "physical"},
                {"id": "symptom-2", "name": "Sleep", "category": "sleep"},
            ]
        ),
    )
    repo = SymptomsRepository(client=mock_client)

    result = await repo.create_log(
        user_id="user-1",
        symptoms=["symptom-1", "symptom-2"],
        free_text_entry="Tired",
        source="cards",
    )

    assert result.id == "log-123"
    assert result.user_id == "user-1"
    assert len(result.symptoms) == 2
    assert result.symptoms[0].name == "Fatigue"


@pytest.mark.asyncio
async def test_create_log_with_logged_at():
    """Test creating a log with explicit logged_at timestamp."""
    logged_at = datetime(2026, 2, 15, 10, 30, 0, tzinfo=timezone.utc)

    mock_client = make_sequential_client(
        # validate_ids
        MagicMock(data=[{"id": "symptom-1"}]),
        # insert
        MagicMock(
            data=[
                {
                    "id": "log-456",
                    "user_id": "user-1",
                    "logged_at": logged_at,
                    "symptoms": ["symptom-1"],
                    "free_text_entry": None,
                    "source": "cards",
                }
            ]
        ),
        # lookup
        MagicMock(
            data=[{"id": "symptom-1", "name": "Hot flash", "category": "vasomotor"}]
        ),
    )
    repo = SymptomsRepository(client=mock_client)

    result = await repo.create_log(
        user_id="user-1",
        symptoms=["symptom-1"],
        logged_at=logged_at,
    )

    assert result.logged_at == logged_at


@pytest.mark.asyncio
async def test_create_log_validation_fails():
    """Test that invalid symptom IDs raise 400."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(ValidationError):
        await repo.create_log(user_id="user-1", symptoms=["invalid-id"])


@pytest.mark.asyncio
async def test_create_log_insert_fails():
    """Test that insert errors raise 500."""
    mock_client = MagicMock()

    # First call is validation
    val_chain = MagicMock()
    val_chain.execute = AsyncMock(return_value=MagicMock(data=[{"id": "symptom-1"}]))
    val_chain.eq.return_value = val_chain
    val_chain.select.return_value = val_chain
    val_chain.in_.return_value = val_chain

    # Second call is insert (which fails)
    ins_chain = MagicMock()
    ins_chain.execute = AsyncMock(side_effect=Exception("Insert failed"))
    ins_chain.insert.return_value = ins_chain

    mock_client.table.side_effect = [val_chain, ins_chain]

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.create_log(user_id="user-1", symptoms=["symptom-1"])


@pytest.mark.asyncio
async def test_create_log_insert_returns_empty():
    """Test that empty insert response raises 500."""
    mock_client = make_sequential_client(
        # validate
        MagicMock(data=[{"id": "symptom-1"}]),
        # insert returns empty
        MagicMock(data=[]),
    )
    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.create_log(user_id="user-1", symptoms=["symptom-1"])


# ---------------------------------------------------------------------------
# get_logs() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_logs_success():
    """Test fetching symptom logs successfully."""
    logged_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    mock_client = make_sequential_client(
        # logs query
        MagicMock(
            data=[
                {
                    "id": "log-1",
                    "user_id": "user-1",
                    "logged_at": logged_at,
                    "symptoms": ["symptom-1", "symptom-2"],
                    "free_text_entry": "Tired today",
                    "source": "cards",
                }
            ]
        ),
        # lookup
        MagicMock(
            data=[
                {"id": "symptom-1", "name": "Fatigue", "category": "physical"},
                {"id": "symptom-2", "name": "Sleep", "category": "sleep"},
            ]
        ),
    )
    repo = SymptomsRepository(client=mock_client)

    logs, count = await repo.get_logs(user_id="user-1")

    assert count == 1
    assert len(logs) == 1
    assert logs[0].id == "log-1"
    assert logs[0].symptoms[0].name == "Fatigue"


@pytest.mark.asyncio
async def test_get_logs_with_date_range():
    """Test fetching logs with date filters."""
    mock_client = make_sequential_client(
        # logs query
        MagicMock(data=[]),
        # lookup
        MagicMock(data=[]),
    )
    repo = SymptomsRepository(client=mock_client)

    logs, count = await repo.get_logs(
        user_id="user-1",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 1),
        limit=25,
    )

    assert count == 0
    assert logs == []


@pytest.mark.asyncio
async def test_get_logs_empty():
    """Test fetching logs when user has none."""
    mock_client = make_sequential_client(
        # logs query
        MagicMock(data=[]),
        # lookup
        MagicMock(data=[]),
    )
    repo = SymptomsRepository(client=mock_client)

    logs, count = await repo.get_logs(user_id="user-1")

    assert count == 0
    assert logs == []


@pytest.mark.asyncio
async def test_get_logs_db_error():
    """Test that DB errors raise 500."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB error"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    mock_client.table.return_value = chain

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_logs(user_id="user-1")


# ---------------------------------------------------------------------------
# _enrich_log() tests
# ---------------------------------------------------------------------------


def test_enrich_log_with_all_symptoms_in_lookup():
    """Test enriching a log when all symptoms are in lookup."""
    row = {
        "id": "log-1",
        "user_id": "user-1",
        "logged_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "symptoms": ["sid-1", "sid-2"],
        "free_text_entry": "Test",
        "source": "cards",
    }
    lookup = {
        "sid-1": SymptomDetail(id="sid-1", name="Fatigue", category="physical"),
        "sid-2": SymptomDetail(id="sid-2", name="Sleep", category="sleep"),
    }

    result = SymptomsRepository._enrich_log(row, lookup)

    assert result.id == "log-1"
    assert len(result.symptoms) == 2
    assert result.symptoms[0].name == "Fatigue"
    assert result.symptoms[1].name == "Sleep"


def test_enrich_log_with_missing_symptoms_in_lookup():
    """Test enriching a log when some symptoms are missing from lookup."""
    row = {
        "id": "log-1",
        "user_id": "user-1",
        "logged_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "symptoms": ["sid-1", "sid-missing"],
        "free_text_entry": None,
        "source": "cards",
    }
    lookup = {
        "sid-1": SymptomDetail(id="sid-1", name="Fatigue", category="physical"),
    }

    result = SymptomsRepository._enrich_log(row, lookup)

    assert len(result.symptoms) == 2
    assert result.symptoms[0].name == "Fatigue"
    # Missing symptom gets fallback
    assert result.symptoms[1].id == "sid-missing"
    assert result.symptoms[1].name == "sid-missing"
    assert result.symptoms[1].category == "unknown"


def test_enrich_log_with_empty_symptoms():
    """Test enriching a log with no symptoms."""
    row = {
        "id": "log-1",
        "user_id": "user-1",
        "logged_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "symptoms": [],
        "free_text_entry": "Just notes",
        "source": "text",
    }
    lookup = {}

    result = SymptomsRepository._enrich_log(row, lookup)

    assert result.symptoms == []
    assert result.free_text_entry == "Just notes"


# ---------------------------------------------------------------------------
# _fetch_lookup() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_lookup_empty():
    """Test that empty ID list returns empty lookup."""
    mock_client = make_sequential_client()
    repo = SymptomsRepository(client=mock_client)

    result = await repo._fetch_lookup([])

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_lookup_success():
    """Test fetching symptom lookup data."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {"id": "sid-1", "name": "Fatigue", "category": "physical"},
                {"id": "sid-2", "name": "Sleep", "category": "sleep"},
            ]
        )
    )
    repo = SymptomsRepository(client=mock_client)

    result = await repo._fetch_lookup(["sid-1", "sid-2"])

    assert "sid-1" in result
    assert result["sid-1"].name == "Fatigue"
    assert "sid-2" in result
    assert result["sid-2"].name == "Sleep"


@pytest.mark.asyncio
async def test_fetch_lookup_partial_results():
    """Test that missing symptoms are omitted from lookup."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {"id": "sid-1", "name": "Fatigue", "category": "physical"},
            ]
        )
    )
    repo = SymptomsRepository(client=mock_client)

    result = await repo._fetch_lookup(["sid-1", "sid-missing"])

    assert "sid-1" in result
    assert "sid-missing" not in result


# ---------------------------------------------------------------------------
# get_logs_with_reference() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_logs_with_reference_returns_logs_and_reference():
    """Should return raw logs with reference data for stats calculations."""
    logs_response = MagicMock()
    logs_response.data = [
        {"symptoms": ["sid-1", "sid-2"]},
        {"symptoms": ["sid-1"]},
    ]

    ref_response = MagicMock()
    ref_response.data = [
        {"id": "sid-1", "name": "Fatigue", "category": "physical"},
        {"id": "sid-2", "name": "Brain Fog", "category": "cognitive"},
    ]

    mock_client = make_sequential_client(logs_response, ref_response)
    repo = SymptomsRepository(client=mock_client)

    logs, ref_lookup = await repo.get_logs_with_reference("user-1")

    assert len(logs) == 2
    assert logs[0]["symptoms"] == ["sid-1", "sid-2"]
    assert "sid-1" in ref_lookup
    assert ref_lookup["sid-1"]["name"] == "Fatigue"
    assert "sid-2" in ref_lookup


@pytest.mark.asyncio
async def test_get_logs_with_reference_no_logs_returns_empty_lookup():
    """Should return empty reference lookup when no logs found."""
    logs_response = MagicMock()
    logs_response.data = []

    mock_client = make_sequential_client(logs_response)
    repo = SymptomsRepository(client=mock_client)

    logs, ref_lookup = await repo.get_logs_with_reference("user-1")

    assert logs == []
    assert ref_lookup == {}


@pytest.mark.asyncio
async def test_get_logs_with_reference_with_date_filters():
    """Should apply date filters correctly."""
    logs_response = MagicMock()
    logs_response.data = [
        {"symptoms": ["sid-1"]},
    ]

    ref_response = MagicMock()
    ref_response.data = [
        {"id": "sid-1", "name": "Fatigue", "category": "physical"},
    ]

    mock_client = make_sequential_client(logs_response, ref_response)
    repo = SymptomsRepository(client=mock_client)

    logs, ref_lookup = await repo.get_logs_with_reference(
        "user-1",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert len(logs) == 1
    assert "sid-1" in ref_lookup


@pytest.mark.asyncio
async def test_get_logs_with_reference_logs_query_fails():
    """Should raise 500 if logs query fails."""
    response = MagicMock()
    response.execute = AsyncMock(side_effect=Exception("DB error"))

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value = response

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_logs_with_reference("user-1")


@pytest.mark.asyncio
async def test_get_logs_with_reference_reference_query_fails():
    """Should raise 500 if reference query fails."""
    logs_response = MagicMock()
    logs_response.data = [
        {"symptoms": ["sid-1"]},
    ]

    ref_response = MagicMock()
    ref_response.execute = AsyncMock(side_effect=Exception("DB error"))

    # First table call returns logs successfully, second fails
    def table_side_effect(name):
        if name == "symptom_logs":
            chain = MagicMock()
            chain.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=logs_response
            )
            chain.select.return_value.eq.return_value.eq.return_value = (
                chain.select.return_value.eq.return_value
            )
            return chain
        else:  # symptoms_reference
            chain = MagicMock()
            chain.select.return_value.in_.return_value = ref_response
            return chain

    mock_client = MagicMock()
    mock_client.table.side_effect = table_side_effect

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_logs_with_reference("user-1")


# ---------------------------------------------------------------------------
# get_logs_for_export() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_logs_for_export_returns_logs_with_all_fields():
    """Should return logs with logged_at, symptoms, free_text_entry for export."""
    logs_response = MagicMock()
    logs_response.data = [
        {
            "logged_at": "2026-02-01T10:00:00Z",
            "symptoms": ["sid-1", "sid-2"],
            "free_text_entry": "Felt tired",
        },
        {
            "logged_at": "2026-02-02T14:30:00Z",
            "symptoms": ["sid-1"],
            "free_text_entry": None,
        },
    ]

    ref_response = MagicMock()
    ref_response.data = [
        {"id": "sid-1", "name": "Fatigue", "category": "physical"},
        {"id": "sid-2", "name": "Brain Fog", "category": "cognitive"},
    ]

    mock_client = make_sequential_client(logs_response, ref_response)
    repo = SymptomsRepository(client=mock_client)

    logs, ref_lookup = await repo.get_logs_for_export(
        "user-1",
        date(2026, 2, 1),
        date(2026, 2, 28),
    )

    assert len(logs) == 2
    assert logs[0]["logged_at"] == "2026-02-01T10:00:00Z"
    assert logs[0]["free_text_entry"] == "Felt tired"
    assert "sid-1" in ref_lookup
    assert ref_lookup["sid-1"]["name"] == "Fatigue"


@pytest.mark.asyncio
async def test_get_logs_for_export_no_logs_returns_empty_lookup():
    """Should return empty reference lookup when no logs found."""
    logs_response = MagicMock()
    logs_response.data = []

    mock_client = make_sequential_client(logs_response)
    repo = SymptomsRepository(client=mock_client)

    logs, ref_lookup = await repo.get_logs_for_export(
        "user-1",
        date(2026, 2, 1),
        date(2026, 2, 28),
    )

    assert logs == []
    assert ref_lookup == {}


@pytest.mark.asyncio
async def test_get_logs_for_export_logs_query_fails():
    """Should raise 500 if logs query fails."""
    response = MagicMock()
    response.execute = AsyncMock(side_effect=Exception("DB error"))

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value = response

    repo = SymptomsRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get_logs_for_export("user-1", date(2026, 2, 1), date(2026, 2, 28))
