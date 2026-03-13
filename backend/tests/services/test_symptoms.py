"""Tests for app/services/symptoms.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import DatabaseError, ValidationError
from app.services.symptoms import validate_symptom_ids


class TestValidateSymptomIds:
    """Tests for validate_symptom_ids() function."""

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_empty_list(self):
        """Test: Empty symptom IDs list returns early without querying."""
        mock_client = AsyncMock()

        # Should return without any error
        await validate_symptom_ids([], mock_client)

        # Verify no query was made
        mock_client.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_all_valid(self):
        """Test: All valid symptom IDs pass validation."""
        mock_client = MagicMock()

        # Set up successful response with all IDs found
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "id-1"},
            {"id": "id-2"},
            {"id": "id-3"},
        ]

        # Set up fluent chain
        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(return_value=mock_response)
        mock_client.table.return_value = chain

        # Should pass without error
        await validate_symptom_ids(["id-1", "id-2", "id-3"], mock_client)

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_deduplicates_before_query(self):
        """Test: Duplicate IDs are deduplicated before querying."""
        mock_client = MagicMock()

        # Set up response for 2 unique IDs
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "id-1"},
            {"id": "id-2"},
        ]

        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(return_value=mock_response)
        mock_client.table.return_value = chain

        # Pass 3 IDs with one duplicate
        await validate_symptom_ids(["id-1", "id-2", "id-1"], mock_client)

        # Verify in_() was called with 2 unique IDs (set, so order may vary)
        chain.in_.assert_called_once()
        call_args = chain.in_.call_args
        passed_ids = set(call_args[0][1])  # Second argument to in_()
        assert passed_ids == {"id-1", "id-2"}

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_invalid_ids_raise_400(self):
        """Test: Invalid symptom IDs raise ValidationError."""
        mock_client = MagicMock()

        # Set up response: only 2 IDs found, but 3 were requested
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "id-1"},
            {"id": "id-2"},
            # id-3 is missing
        ]

        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(return_value=mock_response)
        mock_client.table.return_value = chain

        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await validate_symptom_ids(["id-1", "id-2", "id-3"], mock_client)

        assert "Invalid symptom IDs" in str(exc_info.value)
        assert "id-3" in str(exc_info.value)  # Should show which ID is invalid

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_no_results_found_raise_400(self):
        """Test: No matching IDs raise ValidationError."""
        mock_client = MagicMock()

        # Set up response: no IDs found
        mock_response = MagicMock()
        mock_response.data = []

        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(return_value=mock_response)
        mock_client.table.return_value = chain

        # Should raise ValidationError
        with pytest.raises(ValidationError):
            await validate_symptom_ids(["invalid-id"], mock_client)

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_database_error_raise_500(self):
        """Test: Database query failure raises DatabaseError."""
        mock_client = MagicMock()

        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(side_effect=Exception("Connection failed"))
        mock_client.table.return_value = chain

        # Should raise DatabaseError
        with pytest.raises(DatabaseError) as exc_info:
            await validate_symptom_ids(["id-1"], mock_client)

        assert "Failed to validate" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_symptom_ids_single_valid_id(self):
        """Test: Single valid ID passes validation."""
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.data = [{"id": "hot-flash"}]

        chain = MagicMock()
        chain.select.return_value = chain
        chain.in_.return_value = chain
        chain.execute = AsyncMock(return_value=mock_response)
        mock_client.table.return_value = chain

        # Should pass without error
        await validate_symptom_ids(["hot-flash"], mock_client)
