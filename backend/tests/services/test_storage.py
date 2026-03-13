"""Tests for app/services/storage.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.storage import StorageService


@pytest.fixture
def mock_supabase():
    """Create a mocked Supabase AsyncClient."""
    return MagicMock()


@pytest.fixture
def storage_service(mock_supabase):
    """Create StorageService with mocked Supabase client."""
    return StorageService(mock_supabase)


class TestStorageServiceUploadPdf:
    """Tests for StorageService.upload_pdf()."""

    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, storage_service, mock_supabase):
        """Test: PDF upload succeeds and returns signed URL."""
        # Set up mock storage chain
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        # Mock upload success
        mock_from.upload = AsyncMock()

        # Mock signed URL generation
        mock_signed_response = {"signedURL": "https://signed.url/file.pdf"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_signed_response)

        mock_supabase.storage = mock_storage

        # Execute
        pdf_content = b"PDF content here"
        result = await storage_service.upload_pdf(
            bucket="test-bucket",
            path="user-id/file.pdf",
            content=pdf_content,
            signed_url_expires=3600,
        )

        # Verify
        assert result == "https://signed.url/file.pdf"
        mock_storage.from_.assert_called_with("test-bucket")
        mock_from.upload.assert_called_once()
        mock_from.create_signed_url.assert_called_once_with("user-id/file.pdf", 3600)

    @pytest.mark.asyncio
    async def test_upload_pdf_custom_expiration(self, storage_service, mock_supabase):
        """Test: PDF upload respects custom expiration time."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_from.upload = AsyncMock()
        mock_signed_response = {"signedURL": "https://signed.url"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_signed_response)

        mock_supabase.storage = mock_storage

        # Upload with 7200 second expiration
        await storage_service.upload_pdf(
            bucket="bucket",
            path="file.pdf",
            content=b"data",
            signed_url_expires=7200,
        )

        # Verify create_signed_url was called with 7200
        call_args = mock_from.create_signed_url.call_args
        assert call_args[0][1] == 7200

    @pytest.mark.asyncio
    async def test_upload_pdf_upload_failure(self, storage_service, mock_supabase):
        """Test: Upload failure raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_from.upload = AsyncMock(side_effect=Exception("Upload failed"))
        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.upload_pdf("bucket", "path.pdf", b"content")

        assert "Failed to upload PDF" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_pdf_signed_url_failure(self, storage_service, mock_supabase):
        """Test: Signed URL generation failure raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_from.upload = AsyncMock()  # Upload succeeds
        mock_from.create_signed_url = AsyncMock(
            side_effect=Exception("URL generation failed")
        )
        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.upload_pdf("bucket", "path.pdf", b"content")

        assert "Failed to upload PDF" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_pdf_passes_file_options(self, storage_service, mock_supabase):
        """Test: upload_pdf passes correct file options to Supabase."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_from.upload = AsyncMock()
        mock_signed_response = {"signedURL": "https://signed.url"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_signed_response)

        mock_supabase.storage = mock_storage

        # Upload
        await storage_service.upload_pdf(
            bucket="bucket", path="file.pdf", content=b"data"
        )

        # Verify file_options include content-type and upsert
        call_kwargs = mock_from.upload.call_args[1]
        assert call_kwargs["file_options"]["content-type"] == "application/pdf"
        assert call_kwargs["file_options"]["upsert"] == "true"


class TestStorageServiceCreateSignedUrl:
    """Tests for StorageService.create_signed_url()."""

    @pytest.mark.asyncio
    async def test_create_signed_url_success(self, storage_service, mock_supabase):
        """Test: Signed URL creation succeeds."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_response = {"signedURL": "https://signed.url/file.pdf"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_response)

        mock_supabase.storage = mock_storage

        # Execute
        result = await storage_service.create_signed_url(
            bucket="bucket",
            path="file.pdf",
            expires_in=3600,
        )

        # Verify
        assert result == "https://signed.url/file.pdf"
        mock_from.create_signed_url.assert_called_once_with(
            path="file.pdf", expires_in=3600
        )

    @pytest.mark.asyncio
    async def test_create_signed_url_default_expiration(self, storage_service, mock_supabase):
        """Test: Signed URL uses default 3600 second expiration."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_response = {"signedURL": "https://signed.url"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_response)

        mock_supabase.storage = mock_storage

        # Call without expires_in
        await storage_service.create_signed_url(bucket="bucket", path="file.pdf")

        # Verify default 3600 was used
        call_kwargs = mock_from.create_signed_url.call_args[1]
        assert call_kwargs["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_create_signed_url_custom_expiration(self, storage_service, mock_supabase):
        """Test: Signed URL respects custom expiration time."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_response = {"signedURL": "https://signed.url"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_response)

        mock_supabase.storage = mock_storage

        # Call with custom expires_in
        await storage_service.create_signed_url(
            bucket="bucket", path="file.pdf", expires_in=7200
        )

        # Verify custom value was used
        call_kwargs = mock_from.create_signed_url.call_args[1]
        assert call_kwargs["expires_in"] == 7200

    @pytest.mark.asyncio
    async def test_create_signed_url_missing_signed_url_in_response(
        self, storage_service, mock_supabase
    ):
        """Test: Missing signedURL in response raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        # Response is missing signedURL
        mock_response = {"data": "something"}
        mock_from.create_signed_url = AsyncMock(return_value=mock_response)

        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.create_signed_url("bucket", "file.pdf")

        assert "Failed to generate signed URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_signed_url_empty_response(self, storage_service, mock_supabase):
        """Test: Empty response raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        # Empty response
        mock_from.create_signed_url = AsyncMock(return_value={})

        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.create_signed_url("bucket", "file.pdf")

        assert "Failed to generate signed URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_signed_url_none_response(self, storage_service, mock_supabase):
        """Test: None response raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        # None response
        mock_from.create_signed_url = AsyncMock(return_value=None)

        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.create_signed_url("bucket", "file.pdf")

        assert "Failed to generate signed URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_signed_url_api_error(self, storage_service, mock_supabase):
        """Test: API error raises RuntimeError."""
        mock_storage = MagicMock()
        mock_from = MagicMock()
        mock_storage.from_.return_value = mock_from

        mock_from.create_signed_url = AsyncMock(
            side_effect=Exception("API error: rate limited")
        )

        mock_supabase.storage = mock_storage

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await storage_service.create_signed_url("bucket", "file.pdf")

        assert "Failed to generate signed URL" in str(exc_info.value)
