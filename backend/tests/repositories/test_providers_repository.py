"""Tests for ProvidersRepository."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, status

from app.repositories.providers_repository import ProvidersRepository
from app.models.providers import (
    ProviderCard,
    ProviderSearchResponse,
    ShortlistEntry,
    ShortlistEntryWithProvider,
    StateCount,
)


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
        chain.range.return_value = chain

        return chain

    mock_client.table = MagicMock(side_effect=get_chain)
    return mock_client


# ---------------------------------------------------------------------------
# search_providers() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_providers_requires_state_or_zip():
    """Should raise 400 if neither state nor zip_code provided."""
    client = make_sequential_client()
    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.search_providers(state=None, zip_code=None, city=None)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Either 'state' or 'zip_code' is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_search_providers_by_state():
    """Should fetch providers for given state and apply filters."""
    provider_row = {
        "id": "p-1",
        "name": "Dr. Smith",
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62701",
        "credentials": "MD",
        "practice_name": "Smith Medical",
        "phone": "217-555-1234",
        "website": "https://example.com",
        "nams_certified": True,
        "provider_type": "ob_gyn",
        "specialties": ["menopause"],
        "insurance_accepted": ["Blue Cross", "Aetna"],
        "data_source": "nams",
        "last_verified": "2026-02-01",
    }

    response = MagicMock()
    response.data = [provider_row]

    client = make_sequential_client(response)
    repo = ProvidersRepository(client)

    result = await repo.search_providers(
        state="IL",
        city=None,
        zip_code=None,
        nams_only=True,
        provider_type=None,
        insurance=None,
        page=1,
        page_size=20,
    )

    assert isinstance(result, ProviderSearchResponse)
    assert result.total == 1
    assert len(result.providers) == 1
    assert result.providers[0].id == "p-1"
    assert result.page == 1
    assert result.page_size == 20


@pytest.mark.asyncio
async def test_search_providers_infer_state_from_zip():
    """Should infer state from zip_code when state not provided."""
    zip_response = MagicMock()
    zip_response.data = [{"state": "CA"}]

    provider_row = {
        "id": "p-2",
        "name": "Dr. Jones",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
        "credentials": "MD",
        "practice_name": None,
        "phone": None,
        "website": None,
        "nams_certified": True,
        "provider_type": "internal_medicine",
        "specialties": [],
        "insurance_accepted": [],
        "data_source": "nams",
        "last_verified": None,
    }

    provider_response = MagicMock()
    provider_response.data = [provider_row]

    client = make_sequential_client(zip_response, provider_response)
    repo = ProvidersRepository(client)

    result = await repo.search_providers(
        state=None,
        city=None,
        zip_code="94105",
        nams_only=True,
    )

    assert result.total == 1
    assert result.providers[0].name == "Dr. Jones"


@pytest.mark.asyncio
async def test_search_providers_zip_not_found():
    """Should raise 400 if zip_code not found in database."""
    zip_response = MagicMock()
    zip_response.data = []

    client = make_sequential_client(zip_response)
    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.search_providers(state=None, zip_code="99999")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "No providers found for zip_code" in exc_info.value.detail


@pytest.mark.asyncio
async def test_search_providers_db_error():
    """Should raise 500 on database errors."""
    response = MagicMock()
    response.execute = AsyncMock(side_effect=Exception("DB connection error"))

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value = response

    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.search_providers(state="IL")

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# get_states() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_states_returns_aggregated_counts():
    """Should return states with provider counts."""
    response = MagicMock()
    response.data = [
        {"state": "IL"},
        {"state": "IL"},
        {"state": "CA"},
        {"state": "NY"},
        {"state": "NY"},
        {"state": "NY"},
    ]

    # Mock _fetch_all to return the response data directly
    client = make_sequential_client(response)
    repo = ProvidersRepository(client)
    repo._fetch_all = AsyncMock(return_value=response.data)

    result = await repo.get_states()

    assert len(result) == 3
    assert result[0].state == "CA"  # Alphabetical
    assert result[0].count == 1
    assert result[1].state == "IL"
    assert result[1].count == 2
    assert result[2].state == "NY"
    assert result[2].count == 3


@pytest.mark.asyncio
async def test_get_states_empty():
    """Should return empty list if no states found."""
    response = MagicMock()
    response.data = []

    client = make_sequential_client(response)
    repo = ProvidersRepository(client)
    repo._fetch_all = AsyncMock(return_value=[])

    result = await repo.get_states()

    assert result == []


# ---------------------------------------------------------------------------
# get_insurance_options() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_insurance_options_returns_normalized_list():
    """Should return normalized, deduplicated insurance options."""
    response = MagicMock()
    response.data = [
        {"insurance_accepted": ["Blue Cross", "Aetna"]},
        {"insurance_accepted": ["Blue Cross"]},
        {"insurance_accepted": ["Medicare"]},
    ]

    client = make_sequential_client(response)
    repo = ProvidersRepository(client)
    repo._fetch_all = AsyncMock(return_value=response.data)

    result = await repo.get_insurance_options()

    assert len(result) > 0
    assert all(isinstance(opt, str) for opt in result)


# ---------------------------------------------------------------------------
# get_shortlist() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_shortlist_returns_entries_with_providers():
    """Should return shortlist entries joined with provider data."""
    entries_response = MagicMock()
    entries_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": "Try Tuesday",
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T10:00:00Z",
        }
    ]

    providers_response = MagicMock()
    providers_response.data = [
        {
            "id": "p-1",
            "name": "Dr. Smith",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62701",
            "credentials": "MD",
            "practice_name": "Smith Medical",
            "phone": "217-555-1234",
            "website": "https://example.com",
            "nams_certified": True,
            "provider_type": "ob_gyn",
            "specialties": ["menopause"],
            "insurance_accepted": ["Blue Cross"],
            "data_source": "nams",
            "last_verified": "2026-02-01",
        }
    ]

    client = make_sequential_client(entries_response, providers_response)
    repo = ProvidersRepository(client)

    result = await repo.get_shortlist("user-123")

    assert len(result) == 1
    assert isinstance(result[0], ShortlistEntryWithProvider)
    assert result[0].provider_id == "p-1"
    assert result[0].provider.name == "Dr. Smith"


@pytest.mark.asyncio
async def test_get_shortlist_empty():
    """Should return empty list if no shortlist entries."""
    entries_response = MagicMock()
    entries_response.data = []

    client = make_sequential_client(entries_response)
    repo = ProvidersRepository(client)

    result = await repo.get_shortlist("user-123")

    assert result == []


@pytest.mark.asyncio
async def test_get_shortlist_db_error():
    """Should raise 500 on database errors."""
    response = MagicMock()
    response.execute = AsyncMock(side_effect=Exception("DB error"))

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value = response

    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.get_shortlist("user-123")

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# get_shortlist_ids() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_shortlist_ids_returns_provider_ids():
    """Should return list of provider IDs in shortlist."""
    response = MagicMock()
    response.data = [
        {"provider_id": "p-1"},
        {"provider_id": "p-2"},
        {"provider_id": "p-3"},
    ]

    client = make_sequential_client(response)
    repo = ProvidersRepository(client)

    result = await repo.get_shortlist_ids("user-123")

    assert result == ["p-1", "p-2", "p-3"]


@pytest.mark.asyncio
async def test_get_shortlist_ids_empty():
    """Should return empty list if no shortlist entries."""
    response = MagicMock()
    response.data = []

    client = make_sequential_client(response)
    repo = ProvidersRepository(client)

    result = await repo.get_shortlist_ids("user-123")

    assert result == []


# ---------------------------------------------------------------------------
# add_to_shortlist() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_to_shortlist_creates_new_entry():
    """Should create new shortlist entry and return 201."""
    existing_response = MagicMock()
    existing_response.data = []

    insert_response = MagicMock()
    insert_response.data = [
        {
            "id": "sl-new",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": None,
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T10:00:00Z",
        }
    ]

    client = make_sequential_client(existing_response, insert_response)
    repo = ProvidersRepository(client)

    entry, status_code = await repo.add_to_shortlist("user-123", "p-1")

    assert isinstance(entry, ShortlistEntry)
    assert entry.provider_id == "p-1"
    assert status_code == 201


@pytest.mark.asyncio
async def test_add_to_shortlist_existing_returns_409():
    """Should return existing entry with 409 if already in shortlist."""
    existing_response = MagicMock()
    existing_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": None,
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T10:00:00Z",
        }
    ]

    client = make_sequential_client(existing_response)
    repo = ProvidersRepository(client)

    entry, status_code = await repo.add_to_shortlist("user-123", "p-1")

    assert isinstance(entry, ShortlistEntry)
    assert entry.provider_id == "p-1"
    assert status_code == 409


# ---------------------------------------------------------------------------
# remove_from_shortlist() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_from_shortlist_success():
    """Should delete shortlist entry without error."""
    check_response = MagicMock()
    check_response.data = [{"id": "sl-1"}]

    delete_response = MagicMock()
    delete_response.data = []

    client = make_sequential_client(check_response, delete_response)
    repo = ProvidersRepository(client)

    # Should not raise
    await repo.remove_from_shortlist("user-123", "p-1")


@pytest.mark.asyncio
async def test_remove_from_shortlist_not_found():
    """Should raise 404 if entry not in shortlist."""
    check_response = MagicMock()
    check_response.data = []

    client = make_sequential_client(check_response)
    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.remove_from_shortlist("user-123", "p-1")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not in shortlist" in exc_info.value.detail


# ---------------------------------------------------------------------------
# update_shortlist_entry() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_shortlist_entry_updates_status():
    """Should update status field."""
    check_response = MagicMock()
    check_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": None,
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T10:00:00Z",
        }
    ]

    update_response = MagicMock()
    update_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "called",
            "notes": None,
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T11:00:00Z",
        }
    ]

    client = make_sequential_client(check_response, update_response)
    repo = ProvidersRepository(client)

    result = await repo.update_shortlist_entry(
        "user-123", "p-1", status="called", notes=None
    )

    assert isinstance(result, ShortlistEntry)
    assert result.status == "called"


@pytest.mark.asyncio
async def test_update_shortlist_entry_clears_notes():
    """Should clear notes when passed empty string."""
    check_response = MagicMock()
    check_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": "Call after 5pm",
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T10:00:00Z",
        }
    ]

    update_response = MagicMock()
    update_response.data = [
        {
            "id": "sl-1",
            "user_id": "user-123",
            "provider_id": "p-1",
            "status": "to_call",
            "notes": None,
            "added_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-01T11:00:00Z",
        }
    ]

    client = make_sequential_client(check_response, update_response)
    repo = ProvidersRepository(client)

    result = await repo.update_shortlist_entry("user-123", "p-1", notes="")

    assert result.notes is None


@pytest.mark.asyncio
async def test_update_shortlist_entry_not_found():
    """Should raise 404 if entry not in shortlist."""
    check_response = MagicMock()
    check_response.data = []

    client = make_sequential_client(check_response)
    repo = ProvidersRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        await repo.update_shortlist_entry("user-123", "p-1", status="called")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
