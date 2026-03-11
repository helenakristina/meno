"""Fixtures and helpers for Supabase mocking.

Provides utilities for mocking Supabase client and its fluent query API.
The fluent API (table().select().eq().execute()) is easy to get wrong in tests.
This module provides helpers that are resilient to query chain changes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Optional


def setup_supabase_response(
    mock_client,
    table_name: str = "test_table",
    data: Optional[list[dict]] = None,
    error: Optional[str] = None,
) -> AsyncMock:
    """Configure Supabase mock to return data regardless of query chain length.

    This helper makes mocks resilient to query changes. If someone adds/removes
    .eq(), .select(), or other chain calls, the mock still works correctly.

    Args:
        mock_client: Mocked Supabase AsyncClient.
        table_name: Table name (optional, for clarity).
        data: Data to return from execute(). Defaults to [].
        error: Error message if query should fail. Defaults to None.

    Returns:
        Configured mock_client.

    Example:
        >>> mock_client = AsyncMock()
        >>> setup_supabase_response(mock_client, data=[{"id": "123", "name": "Alice"}])
        >>> # Now this works regardless of chain length:
        >>> await mock_client.table("users").select("*").eq("id", "123").execute()
        # Returns: {"data": [{"id": "123", "name": "Alice"}], "error": None}
    """
    # Create the response object
    result = AsyncMock()
    result.data = data if data is not None else []
    result.error = error

    # Set up the table() call
    table_mock = MagicMock()
    mock_client.table.return_value = table_mock

    # Methods that return the same chain (for chaining)
    chainable_methods = [
        "select",
        "insert",
        "update",
        "upsert",
        "delete",
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "like",
        "ilike",
        "is_",
        "in_",
        "contains",
        "contained_by",
        "range_gt",
        "range_gte",
        "range_lt",
        "range_lte",
        "overlap",
        "fts",
        "plfts",
        "phfts",
        "wfts",
        "order",
        "limit",
        "offset",
        "single",
        "maybe_single",
    ]

    # For each chainable method, make it return the same table_mock
    # This allows unlimited chaining
    for method_name in chainable_methods:
        method_mock = MagicMock(return_value=table_mock)
        setattr(table_mock, method_name, method_mock)

    # execute() returns the result (not chainable)
    table_mock.execute = AsyncMock(return_value=result)

    return mock_client


def setup_supabase_error(
    mock_client,
    error_message: str = "Database error",
) -> AsyncMock:
    """Configure Supabase mock to return an error.

    Args:
        mock_client: Mocked Supabase AsyncClient.
        error_message: Error message to return.

    Returns:
        Configured mock_client.

    Example:
        >>> setup_supabase_error(mock_client, "Connection failed")
        >>> result = await mock_client.table("users").select("*").execute()
        >>> result.error == "Connection failed"
        True
        >>> result.data == []
        True
    """
    return setup_supabase_response(mock_client, data=[], error=error_message)


def setup_supabase_not_found(mock_client) -> AsyncMock:
    """Configure Supabase mock to return empty result (not found).

    Args:
        mock_client: Mocked Supabase AsyncClient.

    Returns:
        Configured mock_client.

    Example:
        >>> setup_supabase_not_found(mock_client)
        >>> result = await mock_client.table("users").eq("id", "999").single().execute()
        >>> result.data == []
        True
    """
    return setup_supabase_response(mock_client, data=[])


@pytest.fixture
def mock_supabase():
    """Provide a pre-configured mock Supabase client.

    The mock is set up to handle common query chains without breaking
    if the query changes.

    Returns:
        MagicMock of Supabase client with sensible defaults.

    Example:
        >>> async def test_fetch_user(mock_supabase):
        ...     setup_supabase_response(mock_supabase, data=[{"id": "123"}])
        ...     repo = UserRepository(mock_supabase)
        ...     user = await repo.get("123")
        ...     assert user.id == "123"
    """
    mock_client = MagicMock()
    # Set default: return empty data (easier to override per test)
    setup_supabase_response(mock_client, data=[])
    return mock_client
