"""Tests for UserRepository."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from app.exceptions import DatabaseError, DuplicateEntityError, EntityNotFoundError

from app.models.users import UserProfile
from app.repositories.user_repository import UserRepository


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
    return UserRepository(client=mock_supabase)


# ============================================================================
# get_context() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_context_success():
    """Test fetching user context (journey stage and age)."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "journey_stage": "perimenopause",
                    "date_of_birth": "1975-03-15",
                }
            ]
        )
    )
    repo = UserRepository(client=mock_client)

    journey_stage, age = await repo.get_context("user-123")

    assert journey_stage == "perimenopause"
    assert age is not None
    assert isinstance(age, int)


@pytest.mark.asyncio
async def test_get_context_missing_data():
    """Test get_context returns defaults when user not found."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    journey_stage, age = await repo.get_context("nonexistent-user")

    assert journey_stage == "unsure"
    assert age is None


@pytest.mark.asyncio
async def test_get_context_missing_journey_stage():
    """Test get_context defaults journey_stage when null."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "journey_stage": None,
                    "date_of_birth": "1975-03-15",
                }
            ]
        )
    )
    repo = UserRepository(client=mock_client)

    journey_stage, age = await repo.get_context("user-123")

    assert journey_stage == "unsure"
    assert age is not None


@pytest.mark.asyncio
async def test_get_context_missing_dob():
    """Test get_context handles missing date_of_birth."""
    mock_client = make_sequential_client(
        MagicMock(
            data=[
                {
                    "journey_stage": "menopause",
                    "date_of_birth": None,
                }
            ]
        )
    )
    repo = UserRepository(client=mock_client)

    journey_stage, age = await repo.get_context("user-123")

    assert journey_stage == "menopause"
    assert age is None


@pytest.mark.asyncio
async def test_get_context_db_error():
    """Test get_context raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError) as exc_info:
        await repo.get_context("user-123")

    assert "Failed to fetch user context" in str(exc_info.value)


# ============================================================================
# get_profile() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_profile_success():
    """Test fetching complete user profile."""
    user_data = {
        "id": "user-123",
        "email": "jane@example.com",
        "date_of_birth": "1975-03-15",
        "journey_stage": "perimenopause",
        "insurance_type": "private",
        "insurance_plan_name": "Blue Cross",
        "onboarding_completed": True,
        "created_at": "2026-01-01T00:00:00",
    }
    mock_client = make_sequential_client(MagicMock(data=[user_data]))
    repo = UserRepository(client=mock_client)

    result = await repo.get_profile("user-123")

    assert isinstance(result, UserProfile)
    assert result.email == "jane@example.com"


@pytest.mark.asyncio
async def test_get_profile_not_found():
    """Test get_profile raises 404 when user not found."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.get_profile("nonexistent-user")

    assert "User not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_profile_db_error():
    """Test get_profile raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError) as exc_info:
        await repo.get_profile("user-123")

    assert "Failed to fetch user profile" in str(exc_info.value)


# ============================================================================
# update_profile() tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_profile_success():
    """Test updating user profile."""
    updated_data = {
        "id": "user-123",
        "email": "jane@example.com",
        "insurance_type": "private",
        "insurance_plan_name": "Blue Cross Updated",
    }
    mock_client = make_sequential_client(MagicMock(data=[updated_data]))
    repo = UserRepository(client=mock_client)

    result = await repo.update_profile(
        "user-123",
        {"insurance_plan_name": "Blue Cross Updated"},
    )

    assert isinstance(result, UserProfile)
    assert result.insurance_plan_name == "Blue Cross Updated"


@pytest.mark.asyncio
async def test_update_profile_not_found():
    """Test update_profile raises 404 when user not found."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.update_profile(
            "nonexistent-user",
            {"insurance_type": "private"},
        )

    assert "User not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_profile_db_error():
    """Test update_profile raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.update.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError) as exc_info:
        await repo.update_profile(
            "user-123",
            {"insurance_type": "private"},
        )

    assert "Failed to update user profile" in str(exc_info.value)


# ============================================================================
# create() tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_success():
    """Test creating a new user profile."""
    created_user = {
        "id": "user-123",
        "email": "jane@example.com",
        "date_of_birth": "1975-03-15",
        "journey_stage": "perimenopause",
        "onboarding_completed": True,
        "created_at": "2026-01-01T00:00:00",
    }
    mock_client = make_sequential_client(MagicMock(data=[created_user]))
    repo = UserRepository(client=mock_client)

    result = await repo.create(
        user_id="user-123",
        email="jane@example.com",
        data={
            "date_of_birth": "1975-03-15",
            "journey_stage": "perimenopause",
            "onboarding_completed": True,
        },
    )

    assert isinstance(result, UserProfile)
    assert result.id == "user-123"
    assert result.email == "jane@example.com"


@pytest.mark.asyncio
async def test_create_duplicate_conflict():
    """Test create raises 409 on duplicate user (conflict)."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(
        side_effect=Exception("duplicate key value violates unique constraint")
    )
    chain.insert.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DuplicateEntityError) as exc_info:
        await repo.create(
            user_id="user-123",
            email="jane@example.com",
            data={"date_of_birth": "1975-03-15"},
        )

    assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_db_error():
    """Test create raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.insert.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError) as exc_info:
        await repo.create(
            user_id="user-123",
            email="jane@example.com",
            data={"date_of_birth": "1975-03-15"},
        )

    assert "Failed to create user profile" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_no_data_returned():
    """Test create raises 500 when Supabase returns no data."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.create(
            user_id="user-123",
            email="jane@example.com",
            data={"date_of_birth": "1975-03-15"},
        )


# ============================================================================
# get() tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_success():
    """Test fetching single user by ID."""
    user_data = {
        "id": "user-123",
        "email": "jane@example.com",
        "date_of_birth": "1975-03-15",
    }
    mock_client = make_sequential_client(MagicMock(data=[user_data]))
    repo = UserRepository(client=mock_client)

    result = await repo.get("user-123")

    assert isinstance(result, UserProfile)
    assert result.id == "user-123"


@pytest.mark.asyncio
async def test_get_not_found():
    """Test get returns None when user not found."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    result = await repo.get("nonexistent-user")

    assert result is None


@pytest.mark.asyncio
async def test_get_db_error():
    """Test get raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.select.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError):
        await repo.get("user-123")


# ============================================================================
# delete() tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_success():
    """Test deleting a user."""
    mock_client = make_sequential_client(MagicMock(data=[{"id": "user-123"}]))
    repo = UserRepository(client=mock_client)

    await repo.delete("user-123")

    mock_client.table.assert_called_with("users")


@pytest.mark.asyncio
async def test_delete_not_found():
    """Test delete raises 404 when user not found."""
    mock_client = make_sequential_client(MagicMock(data=[]))
    repo = UserRepository(client=mock_client)

    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.delete("nonexistent-user")

    assert "User not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_db_error():
    """Test delete raises 500 on database error."""
    mock_client = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(side_effect=Exception("DB down"))
    chain.eq.return_value = chain
    chain.delete.return_value = chain
    mock_client.table.return_value = chain

    repo = UserRepository(client=mock_client)

    with pytest.raises(DatabaseError) as exc_info:
        await repo.delete("user-123")

    assert "Failed to delete user" in str(exc_info.value)


# ============================================================================
# _calculate_age() tests
# ============================================================================


def test_calculate_age_simple():
    """Test age calculation with simple case."""
    from app.utils.dates import calculate_age

    dob = "1975-03-15"
    age = calculate_age(dob)
    # Age depends on today's date, so just verify it's reasonable
    assert age >= 50
    assert age <= 51  # Assuming current year is around 2026


def test_calculate_age_birthday_not_occurred_yet():
    """Test age calculation when birthday hasn't occurred yet this year."""
    from app.utils.dates import calculate_age

    # Someone born on Dec 1, 1980
    dob = "1980-12-01"
    age = calculate_age(dob)
    # Should be 45 or 46 depending on current date
    assert 45 <= age <= 46


def test_calculate_age_birthday_already_occurred():
    """Test age calculation when birthday already occurred this year."""
    from app.utils.dates import calculate_age

    # Someone born on Jan 1, 1975
    dob = "1975-01-01"
    age = calculate_age(dob)
    # Should be 51 or 50 depending on whether Jan 1 has passed
    assert 50 <= age <= 51
