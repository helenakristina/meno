import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import CurrentUser, get_symptoms_repo
from app.models.symptoms import (
    CooccurrenceStatsResponse,
    FrequencyStatsResponse,
    SymptomLogCreate,
    SymptomLogList,
    SymptomLogResponse,
)
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.stats import calculate_cooccurrence_stats, calculate_frequency_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])




# ---------------------------------------------------------------------------
# POST /api/symptoms/logs
# ---------------------------------------------------------------------------


@router.post(
    "/logs",
    response_model=SymptomLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a symptom log",
    description="Store a new symptom log entry for the authenticated user.",
)
async def create_symptom_log(
    payload: SymptomLogCreate,
    user_id: CurrentUser,
    symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo),
) -> SymptomLogResponse:
    """Create a symptom log entry for the authenticated user.

    The user_id is always derived from the validated JWT — callers cannot
    log on behalf of another user. Supabase RLS enforces this at the
    database level as a second layer of defense.

    Raises:
        HTTPException: 400 if any symptom ID is not found in symptoms_reference.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 422 if the payload violates model constraints.
        HTTPException: 500 if the database insert fails.
    """
    return await symptoms_repo.create_log(
        user_id=user_id,
        symptoms=payload.symptoms,
        free_text_entry=payload.free_text_entry,
        source=payload.source,
        logged_at=payload.logged_at,
    )


# ---------------------------------------------------------------------------
# GET /api/symptoms/logs
# ---------------------------------------------------------------------------


@router.get(
    "/logs",
    response_model=SymptomLogList,
    status_code=status.HTTP_200_OK,
    summary="List symptom logs",
    description="Retrieve symptom logs for the authenticated user with optional date filtering.",
)
async def get_symptom_logs(
    user_id: CurrentUser,
    symptoms_repo: SymptomsRepository = Depends(get_symptoms_repo),
    start_date: date | None = Query(
        default=None,
        description="Include logs on or after this date (UTC, ISO 8601)",
    ),
    end_date: date | None = Query(
        default=None,
        description="Include logs on or before this date (UTC, ISO 8601)",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of logs to return (1–100, default 50)",
    ),
) -> SymptomLogList:
    """Return symptom logs for the authenticated user, ordered newest-first.

    Date filters are inclusive and cover the full UTC day (00:00:00–23:59:59).

    Raises:
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 422 if any query parameter fails validation.
        HTTPException: 500 if the database query fails.
    """
    logs, count = await symptoms_repo.get_logs(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return SymptomLogList(logs=logs, count=count, limit=limit)


# ---------------------------------------------------------------------------
# GET /api/symptoms/stats/frequency
# ---------------------------------------------------------------------------


@router.get(
    "/stats/frequency",
    response_model=FrequencyStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Symptom frequency statistics",
    description=(
        "Return how often each symptom was logged in the given date range, "
        "sorted most-to-least frequent. Defaults to the last 30 days."
    ),
)
async def get_frequency_stats(
    user_id: CurrentUser,
    symptoms_repo: Annotated[SymptomsRepository, Depends(get_symptoms_repo)],
    start_date: date | None = Query(
        default=None,
        description="Start of date range (UTC, ISO 8601). Defaults to 30 days ago.",
    ),
    end_date: date | None = Query(
        default=None,
        description="End of date range (UTC, ISO 8601). Defaults to today.",
    ),
) -> FrequencyStatsResponse:
    """Return per-symptom occurrence counts for the authenticated user.

    Counts are total occurrences across all logs in the date range — not
    unique days. A symptom appearing in 3 separate logs contributes 3 to its
    count. Results are sorted by count descending.

    Raises:
        HTTPException: 400 if start_date is after end_date.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 422 if any query parameter fails validation.
        HTTPException: 500 if the database query fails.
    """
    today = date.today()
    effective_end = end_date or today
    effective_start = start_date or (today - timedelta(days=30))

    if effective_start > effective_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date",
        )

    # Fetch logs and reference data for the date range
    rows, ref_lookup = await symptoms_repo.get_logs_with_reference(
        user_id=user_id,
        start_date=effective_start,
        end_date=effective_end,
    )

    total_logs = len(rows)

    # If no logs found, return empty stats response
    if not rows or not ref_lookup:
        logger.info(
            "No symptoms found for user %s in range %s–%s",
            user_id,
            effective_start,
            effective_end,
        )
        return FrequencyStatsResponse(
            stats=[],
            date_range_start=effective_start,
            date_range_end=effective_end,
            total_logs=total_logs,
        )

    # Calculate frequency stats
    stats = calculate_frequency_stats(rows, ref_lookup)

    logger.info(
        "Frequency stats: user=%s range=%s–%s distinct_symptoms=%d total_logs=%d",
        user_id,
        effective_start,
        effective_end,
        len(stats),
        total_logs,
    )
    return FrequencyStatsResponse(
        stats=stats,
        date_range_start=effective_start,
        date_range_end=effective_end,
        total_logs=total_logs,
    )


# ---------------------------------------------------------------------------
# GET /api/symptoms/stats/cooccurrence
# ---------------------------------------------------------------------------

@router.get(
    "/stats/cooccurrence",
    response_model=CooccurrenceStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Symptom co-occurrence statistics",
    description=(
        "Return symptom pairs that occur together above a minimum threshold, "
        "sorted by co-occurrence rate descending. Defaults to the last 30 days."
    ),
)
async def get_cooccurrence_stats(
    user_id: CurrentUser,
    symptoms_repo: Annotated[SymptomsRepository, Depends(get_symptoms_repo)],
    start_date: date | None = Query(
        default=None,
        description="Start of date range (UTC, ISO 8601). Defaults to 30 days ago.",
    ),
    end_date: date | None = Query(
        default=None,
        description="End of date range (UTC, ISO 8601). Defaults to today.",
    ),
    min_threshold: int = Query(
        default=2,
        ge=1,
        description="Minimum number of co-occurrences required to include a pair.",
    ),
) -> CooccurrenceStatsResponse:
    """Return symptom pairs that appear together above a minimum count threshold.

    For each qualifying pair (A, B) the rate is A's perspective:
    co-occurrences / total logs containing A.  Pairs are ordered consistently
    by sorting the two IDs so (A, B) and (B, A) are never double-counted.

    Only logs with two or more symptoms contribute to pair counts; single-
    symptom logs are ignored.  Returns at most 10 pairs (highest rate first).

    Raises:
        HTTPException: 400 if start_date is after end_date.
        HTTPException: 401 if the request is not authenticated.
        HTTPException: 422 if any query parameter fails validation.
        HTTPException: 500 if the database query fails.
    """
    today = date.today()
    effective_end = end_date or today
    effective_start = start_date or (today - timedelta(days=30))

    if effective_start > effective_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date",
        )

    # Fetch logs and reference data for the date range
    rows, ref_lookup = await symptoms_repo.get_logs_with_reference(
        user_id=user_id,
        start_date=effective_start,
        end_date=effective_end,
    )

    total_logs = len(rows)
    logger.debug(
        "Co-occurrence: fetched %d logs for user %s range %s–%s",
        total_logs,
        user_id,
        effective_start,
        effective_end,
    )

    # If no logs or reference data found, return empty response
    if not rows or not ref_lookup:
        logger.info(
            "Co-occurrence: no pairs above threshold=%d for user %s",
            min_threshold,
            user_id,
        )
        return CooccurrenceStatsResponse(
            pairs=[],
            date_range_start=effective_start,
            date_range_end=effective_end,
            total_logs=total_logs,
            min_threshold=min_threshold,
        )

    # Calculate cooccurrence stats
    pairs = calculate_cooccurrence_stats(rows, ref_lookup, min_threshold=min_threshold)

    logger.info(
        "Co-occurrence stats: user=%s range=%s–%s threshold=%d returned=%d",
        user_id,
        effective_start,
        effective_end,
        min_threshold,
        len(pairs),
    )
    return CooccurrenceStatsResponse(
        pairs=pairs,
        date_range_start=effective_start,
        date_range_end=effective_end,
        total_logs=total_logs,
        min_threshold=min_threshold,
    )
