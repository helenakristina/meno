"""ExportService — orchestrates all symptom data export operations.

Handles PDF and CSV export flows:
- export_as_pdf(): fetch data, generate LLM content, build PDF, upload, record
- export_as_csv(): fetch data, build CSV, upload, record
- get_export_history(): return paginated export audit trail

Routes become thin wrappers that call one method and return the result.
"""

import csv
import logging
from datetime import date, datetime
from io import StringIO
from typing import Optional

from app.exceptions import DatabaseError, ValidationError
from app.models.export import ExportRequest, ExportResponse
from app.repositories.export_repository import ExportRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.llm import LLMService
from app.services.medication_base import MedicationServiceBase
from app.services.pdf import PdfService
from app.services.storage import StorageService
from app.utils.logging import hash_user_id
from app.utils.stats import calculate_cooccurrence_stats, calculate_frequency_stats

logger = logging.getLogger(__name__)


class ExportService:
    """Orchestrates symptom data exports (PDF and CSV).

    Raises domain exceptions (ValidationError, DatabaseError) that routes
    convert to HTTP responses via global exception handlers.
    """

    def __init__(
        self,
        symptoms_repo: SymptomsRepository,
        export_repo: ExportRepository,
        pdf_service: PdfService,
        storage_service: StorageService,
        llm_service: LLMService,
        medication_service: Optional[MedicationServiceBase] = None,
    ):
        self.symptoms_repo = symptoms_repo
        self.export_repo = export_repo
        self.pdf_service = pdf_service
        self.storage_service = storage_service
        self.llm_service = llm_service
        self.medication_service = medication_service

    # -------------------------------------------------------------------------
    # PDF export
    # -------------------------------------------------------------------------

    async def export_as_pdf(
        self,
        user_id: str,
        export_params: ExportRequest,
    ) -> ExportResponse:
        """Orchestrate PDF export.

        1. Validate date range
        2. Fetch symptom logs
        3. Calculate statistics
        4. Call LLM for summary and provider questions
        5. Build PDF via PdfService
        6. Upload to Supabase Storage
        7. Record export (non-critical)
        8. Return ExportResponse with signed URL

        Args:
            user_id: Authenticated user ID.
            export_params: Date range for the export.

        Returns:
            ExportResponse with signed_url and filename.

        Raises:
            ValidationError: Invalid date range or no logs in range.
            DatabaseError: LLM or storage operation failed.
        """
        self._validate_date_range(export_params.date_range_start, export_params.date_range_end)

        rows, ref_lookup = await self.symptoms_repo.get_logs_for_export(
            user_id,
            export_params.date_range_start,
            export_params.date_range_end,
        )

        if not rows:
            raise ValidationError("No symptom logs found for the selected date range")

        freq_stats = calculate_frequency_stats(rows, ref_lookup)
        coocc_pairs = calculate_cooccurrence_stats(rows, ref_lookup, min_threshold=2)

        logger.info(
            "PDF export stats: user=%s range=%s–%s logs=%d freq=%d pairs=%d",
            hash_user_id(user_id),
            export_params.date_range_start,
            export_params.date_range_end,
            len(rows),
            len(freq_stats),
            len(coocc_pairs),
        )

        try:
            ai_summary = await self.llm_service.generate_symptom_summary(
                freq_stats,
                coocc_pairs,
                (export_params.date_range_start, export_params.date_range_end),
            )
            questions = await self.llm_service.generate_provider_questions(
                freq_stats, coocc_pairs
            )
        except Exception as exc:
            logger.error(
                "LLM call failed for PDF export: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError("Failed to generate AI content for the report") from exc

        # Fetch medications active during the export range — supplementary, degrade gracefully
        current_medications: list = []
        if self.medication_service is not None:
            try:
                current_medications = await self.medication_service.list_active_during(
                    user_id,
                    export_params.date_range_start,
                    export_params.date_range_end,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch medications for PDF export: user=%s error=%s",
                    hash_user_id(user_id),
                    exc,
                )

        try:
            pdf_bytes = self.pdf_service.build_export_pdf(
                date_range_start=export_params.date_range_start,
                date_range_end=export_params.date_range_end,
                ai_summary=ai_summary,
                frequency_stats=freq_stats,
                cooccurrence_pairs=coocc_pairs,
                provider_questions=questions,
                current_medications=current_medications or None,
            )
        except Exception as exc:
            logger.error(
                "PDF rendering failed: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError("Failed to generate PDF") from exc

        filename = (
            f"meno-summary-{export_params.date_range_start}-{export_params.date_range_end}.pdf"
        )
        storage_path = f"{user_id}/{filename}"

        try:
            signed_url = await self.storage_service.upload_pdf(
                bucket="exports",
                path=storage_path,
                content=pdf_bytes,
            )
        except Exception as exc:
            logger.error(
                "PDF upload failed: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError("Failed to upload PDF") from exc

        logger.info(
            "PDF export complete: user=%s size=%d bytes",
            hash_user_id(user_id),
            len(pdf_bytes),
        )

        await self._record_export_safe(
            user_id,
            "pdf",
            export_params.date_range_start,
            export_params.date_range_end,
        )

        return ExportResponse(signed_url=signed_url, filename=filename, export_type="pdf")

    # -------------------------------------------------------------------------
    # CSV export
    # -------------------------------------------------------------------------

    async def export_as_csv(
        self,
        user_id: str,
        export_params: ExportRequest,
    ) -> ExportResponse:
        """Orchestrate CSV export.

        1. Validate date range
        2. Fetch symptom logs
        3. Build CSV
        4. Upload to Supabase Storage
        5. Record export (non-critical)
        6. Return ExportResponse with signed URL

        Args:
            user_id: Authenticated user ID.
            export_params: Date range for the export.

        Returns:
            ExportResponse with signed_url and filename.

        Raises:
            ValidationError: Invalid date range or no logs in range.
            DatabaseError: Storage operation failed.
        """
        self._validate_date_range(export_params.date_range_start, export_params.date_range_end)

        rows, ref_lookup = await self.symptoms_repo.get_logs_for_export(
            user_id,
            export_params.date_range_start,
            export_params.date_range_end,
        )

        if not rows:
            raise ValidationError("No symptom logs found for the selected date range")

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "symptoms", "free_text_notes"])

        for row in rows:
            log_date = self._parse_log_date(row.get("logged_at", ""))
            symptom_ids = row.get("symptoms") or []
            symptom_names = ", ".join(
                ref_lookup[sid]["name"] for sid in symptom_ids if sid in ref_lookup
            )
            free_text = row.get("free_text_entry") or ""
            writer.writerow([log_date, symptom_names, free_text])

        csv_bytes = output.getvalue().encode()

        filename = (
            f"meno-logs-{export_params.date_range_start}-{export_params.date_range_end}.csv"
        )
        storage_path = f"{user_id}/{filename}"

        try:
            signed_url = await self.storage_service.upload_file(
                bucket="exports",
                path=storage_path,
                content=csv_bytes,
                content_type="text/csv",
            )
        except Exception as exc:
            logger.error(
                "CSV upload failed: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError("Failed to upload CSV") from exc

        logger.info(
            "CSV export complete: user=%s logs=%d size=%d bytes",
            hash_user_id(user_id),
            len(rows),
            len(csv_bytes),
        )

        await self._record_export_safe(
            user_id,
            "csv",
            export_params.date_range_start,
            export_params.date_range_end,
        )

        return ExportResponse(signed_url=signed_url, filename=filename, export_type="csv")

    # -------------------------------------------------------------------------
    # Export history
    # -------------------------------------------------------------------------

    async def get_export_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Return paginated export history for the user.

        Args:
            user_id: Authenticated user ID.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            Dict with 'exports', 'total', 'has_more', 'limit', 'offset'.

        Raises:
            DatabaseError: If the query fails.
        """
        records, total = await self.export_repo.get_export_history(user_id, limit, offset)
        return {
            "exports": records,
            "total": total,
            "has_more": offset + limit < total,
            "limit": limit,
            "offset": offset,
        }

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _validate_date_range(self, start: date, end: date) -> None:
        """Raise ValidationError if the date range is invalid."""
        today = date.today()
        if start > end:
            raise ValidationError("date_range_start must be on or before date_range_end")
        if end > today:
            raise ValidationError("date_range_end cannot be in the future")

    def _parse_log_date(self, logged_at: str) -> str:
        """Extract YYYY-MM-DD from an ISO 8601 datetime string."""
        try:
            dt = datetime.fromisoformat(logged_at.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return logged_at[:10]

    async def _record_export_safe(
        self,
        user_id: str,
        export_type: str,
        date_range_start: date,
        date_range_end: date,
    ) -> None:
        """Record export in database, logging a warning on failure (non-critical)."""
        try:
            await self.export_repo.record_export(
                user_id=user_id,
                export_type=export_type,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record %s export for user=%s: %s",
                export_type,
                hash_user_id(user_id),
                exc,
            )
