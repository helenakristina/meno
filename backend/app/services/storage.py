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

    async def upload_pdf(
        self, bucket: str, path: str, content: bytes, signed_url_expires: int = 3600
    ) -> str:
        """Upload a PDF to Supabase Storage and return a signed URL.

        Uses signed URLs (not public URLs) so the bucket can remain private.
        The signed URL is valid for `signed_url_expires` seconds (default 1 hour).

        Args:
            bucket: Storage bucket name (e.g., "appointment-prep").
            path: File path within the bucket (e.g., "user-id/appointment-id/file.pdf").
            content: PDF file content as bytes.
            signed_url_expires: Seconds until the signed URL expires (default 3600 = 1 hour).

        Returns:
            Signed URL to the uploaded file (time-limited).

        Raises:
            RuntimeError: If the upload or URL generation fails.
        """
        try:
            # Upload file (upsert=True overwrites on regenerate)
            await self.client.storage.from_(bucket).upload(
                path=path,
                file=content,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )
            logger.info(
                "PDF uploaded: bucket=%s path=%s size=%d bytes",
                bucket,
                path,
                len(content),
            )

            # Generate signed URL (works with private buckets)
            signed = await self.client.storage.from_(bucket).create_signed_url(
                path, signed_url_expires
            )
            signed_url: str = signed["signedURL"]
            logger.info("Signed URL created (expires %ds): %s", signed_url_expires, signed_url)
            return signed_url

        except Exception as exc:
            logger.error(
                "Failed to upload PDF: bucket=%s path=%s error=%s",
                bucket,
                path,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Failed to upload PDF: {exc}") from exc

    async def create_signed_url(
        self,
        bucket: str,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        """Create a signed URL for accessing a file in storage.

        Args:
            bucket: Bucket name.
            path: File path in bucket.
            expires_in: URL expiration time in seconds (default 1 hour).

        Returns:
            Signed URL string.

        Raises:
            RuntimeError: If URL generation fails.
        """
        try:
            response = await self.client.storage.from_(bucket).create_signed_url(
                path=path,
                expires_in=expires_in,
            )

            if response and "signedURL" in response:
                logger.debug(
                    "Generated signed URL: bucket=%s path=%s expires=%d",
                    bucket,
                    path,
                    expires_in,
                )
                return response["signedURL"]

            logger.error(
                "Failed to generate signed URL: bucket=%s path=%s",
                bucket,
                path,
            )
            raise RuntimeError("Failed to generate signed URL")

        except Exception as exc:
            logger.error(
                "Error generating signed URL: %s",
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Failed to generate signed URL: {exc}") from exc
