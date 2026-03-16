import logging

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, get_period_service
from app.models.period import (
    CreatePeriodLogResponse,
    CycleAnalysisResponse,
    PeriodLogCreate,
    PeriodLogListResponse,
    PeriodLogResponse,
    PeriodLogUpdate,
)
from app.services.period import PeriodService
from app.utils.logging import hash_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/period", tags=["period"])


@router.post(
    "/logs",
    response_model=CreatePeriodLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a period log",
)
async def create_period_log(
    payload: PeriodLogCreate,
    user_id: CurrentUser,
    service: PeriodService = Depends(get_period_service),
) -> CreatePeriodLogResponse:
    """Create a new period log entry.

    Returns the log and a bleeding_alert flag (True if user is post-menopause).

    Raises:
        HTTPException: 400 if period_start is in the future.
        HTTPException: 401 if unauthenticated.
        HTTPException: 500 for unexpected failures.
    """
    result = await service.create_log(user_id, payload)
    logger.info("Period log created: user=%s", hash_user_id(user_id))
    return result


@router.get(
    "/logs",
    response_model=PeriodLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List period logs",
)
async def list_period_logs(
    user_id: CurrentUser,
    start_date: str | None = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    service: PeriodService = Depends(get_period_service),
) -> PeriodLogListResponse:
    """Fetch period logs with optional date range filtering.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 500 for unexpected failures.
    """
    return await service.get_logs(user_id, start_date, end_date)


@router.patch(
    "/logs/{log_id}",
    response_model=PeriodLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a period log",
)
async def update_period_log(
    log_id: str,
    payload: PeriodLogUpdate,
    user_id: CurrentUser,
    service: PeriodService = Depends(get_period_service),
) -> PeriodLogResponse:
    """Update an existing period log.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if the log does not exist.
        HTTPException: 500 for unexpected failures.
    """
    return await service.update_log(user_id, log_id, payload)


@router.delete(
    "/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a period log",
)
async def delete_period_log(
    log_id: str,
    user_id: CurrentUser,
    service: PeriodService = Depends(get_period_service),
) -> None:
    """Delete a period log and recalculate cycle analysis.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 404 if the log does not exist.
        HTTPException: 500 for unexpected failures.
    """
    await service.delete_log(user_id, log_id)
    logger.info("Period log deleted: user=%s", hash_user_id(user_id))


@router.get(
    "/analysis",
    response_model=CycleAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cycle analysis",
)
async def get_cycle_analysis(
    user_id: CurrentUser,
    service: PeriodService = Depends(get_period_service),
) -> CycleAnalysisResponse:
    """Get cycle analysis including inferred stage and sufficiency flag.

    Raises:
        HTTPException: 401 if unauthenticated.
        HTTPException: 500 for unexpected failures.
    """
    return await service.get_analysis(user_id)
