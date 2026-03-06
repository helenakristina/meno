"""Service for uploading files to Supabase Storage.

Handles PDF uploads and URL retrieval for appointment prep outputs.
"""

import logging

from supabase import AsyncClient

logger = logging.getLogger(__name__)


class StorageService:
    """Upload files to Supabase Storage and retrieve public URLs."""

    def __init__(self, client: AsyncClient):
        """Initialize with Supabase client.

        Args:
            client: Supabase AsyncClient for storage operations.
        """
        self.client = client

    async def upload_pdf(self, bucket: str, path: str, content: bytes) -> str:
        """Upload a PDF file to Supabase Storage and return its public URL.

        Args:
            bucket: Storage bucket name (e.g., "appointment-prep").
            path: File path within the bucket (e.g., "user-id/appointment-id/file.pdf").
            content: PDF file content as bytes.

        Returns:
            Public URL to the uploaded file.

        Raises:
            RuntimeError: If the upload or URL retrieval fails.
        """
        try:
            # Upload file
            await self.client.storage.from_(bucket).upload(
                path=path,
                file=content,
                file_options={"content-type": "application/pdf"},
            )
            logger.info(
                "PDF uploaded: bucket=%s path=%s size=%d bytes",
                bucket,
                path,
                len(content),
            )

            # Get public URL
            url_response = self.client.storage.from_(bucket).get_public_url(path)
            public_url: str = url_response
            logger.info("Public URL retrieved: %s", public_url)
            return public_url

        except Exception as exc:
            logger.error(
                "Failed to upload PDF: bucket=%s path=%s error=%s",
                bucket,
                path,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Failed to upload PDF: {exc}") from exc
