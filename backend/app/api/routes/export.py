"""Export endpoints: PDF provider summary and CSV raw data download.

POST /api/export/pdf  — Generate a clinical PDF report.
POST /api/export/csv  — Export raw symptom logs as CSV.
GET  /api/export/history — Paginated export audit trail.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, get_export_service
from app.models.export import ExportRequest, ExportResponse
from app.services.export import ExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post(
    "/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export symptom summary as PDF",
    description=(
        "Generate a clinical PDF report for a healthcare provider visit. "
        "Includes an AI-written symptom pattern summary, frequency table, "
        "co-occurrence highlights, and suggested questions to discuss."
    ),
)
async def export_pdf(
    payload: ExportRequest,
    user_id: CurrentUser,
    service: Annotated[ExportService, Depends(get_export_service)],
) -> ExportResponse:
    """Export symptom data as PDF. Returns a signed download URL."""
    return await service.export_as_pdf(user_id, payload)


@router.post(
    "/csv",
    status_code=status.HTTP_200_OK,
    summary="Export symptom logs as CSV",
    description=(
        "Download raw symptom logs as a CSV file with columns: "
        "date, symptoms (comma-separated), free_text_notes."
    ),
)
async def export_csv(
    payload: ExportRequest,
    user_id: CurrentUser,
    service: Annotated[ExportService, Depends(get_export_service)],
) -> ExportResponse:
    """Export symptom data as CSV. Returns a signed download URL."""
    return await service.export_as_csv(user_id, payload)


@router.get(
    "/history",
    status_code=status.HTTP_200_OK,
    summary="Get export history",
)
async def get_export_history(
    user_id: CurrentUser,
    service: Annotated[ExportService, Depends(get_export_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """Return paginated export history for the authenticated user."""
    return await service.get_export_history(user_id, limit, offset)
