import itertools
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import AsyncClient

from app.core.supabase import get_client
from app.models.symptoms import (
    CooccurrenceStatsResponse,
    FrequencyStatsResponse,
    SymptomDetail,
    SymptomFrequency,
    SymptomLogCreate,
    SymptomLogList,
    SymptomLogResponse,
    SymptomPair,
)
from app.services.symptoms import validate_symptom_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    client: AsyncClient = Depends(get_client),
) -> str:
    """Validate the Bearer JWT and return the authenticated user's UUID.

    Raises:
        HTTPException: 401 if the Authorization header is missing,
            malformed, or the token is invalid or expired.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    try:
        response = await client.auth.get_user(token)
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(response.user.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token validation failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Type aliases for cleaner route signatures
CurrentUser = Annotated[str, Depends(get_current_user_id)]
SupabaseClient = Annotated[AsyncClient, Depends(get_client)]


# ---------------------------------------------------------------------------
# Symptom enrichment helpers
# ---------------------------------------------------------------------------


async def _fetch_symptom_lookup(
    symptom_ids: list[str], client: AsyncClient
) -> dict[str, SymptomDetail]:
    """Query symptoms_reference for the given IDs and return an id → SymptomDetail map.

    Missing IDs are silently omitted from the result; callers handle the
    fallback so we avoid a tight coupling between this helper and logging policy.
    """
    if not symptom_ids:
        return {}
    response = (
        await client.table("symptoms_reference")
        .select("id, name, category")
        .in_("id", symptom_ids)
        .execute()
    )
    return {
        row["id"]: SymptomDetail(
            id=row["id"], name=row["name"], category=row["category"]
        )
        for row in (response.data or [])
    }


def _enrich_log(row: dict, lookup: dict[str, SymptomDetail]) -> SymptomLogResponse:
    """Build a SymptomLogResponse, resolving symptom IDs to SymptomDetail objects.

    Any ID not present in the lookup is a data-integrity anomaly: a warning is
    logged and a fallback SymptomDetail with name=id and category="unknown" is
    used so the log is never silently dropped.
    """
    enriched: list[SymptomDetail] = []
    for sid in row.get("symptoms") or []:
        if sid in lookup:
            enriched.append(lookup[sid])
        else:
            logger.warning(
                "Symptom ID %s not found in symptoms_reference (data integrity issue)",
                sid,
            )
            enriched.append(SymptomDetail(id=sid, name=sid, category="unknown"))
    return SymptomLogResponse(
        id=row["id"],
        user_id=row["user_id"],
        logged_at=row["logged_at"],
        symptoms=enriched,
        free_text_entry=row.get("free_text_entry"),
        source=row["source"],
    )


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
    client: SupabaseClient,
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
    await validate_symptom_ids(payload.symptoms, client)

    row: dict = {
        "user_id": user_id,
        "symptoms": payload.symptoms,
        "free_text_entry": payload.free_text_entry,
        "source": payload.source,
    }
    if payload.logged_at is not None:
        row["logged_at"] = payload.logged_at.isoformat()

    try:
        response = await client.table("symptom_logs").insert(row).execute()
    except Exception as exc:
        logger.error(
            "DB insert failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create symptom log",
        )

    if not response.data:
        logger.error("Supabase returned no data after insert for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create symptom log",
        )

    created = response.data[0]
    try:
        lookup = await _fetch_symptom_lookup(created.get("symptoms") or [], client)
    except Exception as exc:
        logger.error(
            "Failed to enrich symptom data for log %s: %s",
            created["id"],
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create symptom log",
        )
    logger.info("Symptom log created: id=%s user=%s", created["id"], user_id)
    return _enrich_log(created, lookup)


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
    client: SupabaseClient,
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
    rows: list[dict] = []
    lookup: dict[str, SymptomDetail] = {}
    try:
        query = client.table("symptom_logs").select("*").eq("user_id", user_id)

        if start_date is not None:
            start_dt = datetime(
                start_date.year,
                start_date.month,
                start_date.day,
                tzinfo=timezone.utc,
            )
            query = query.gte("logged_at", start_dt.isoformat())

        if end_date is not None:
            end_dt = datetime(
                end_date.year,
                end_date.month,
                end_date.day,
                23,
                59,
                59,
                tzinfo=timezone.utc,
            )
            query = query.lte("logged_at", end_dt.isoformat())

        query = query.order("logged_at", desc=True).limit(limit)
        response = await query.execute()

        rows = response.data or []
        unique_ids = list(
            {sid for row in rows for sid in (row.get("symptoms") or [])}
        )
        lookup = await _fetch_symptom_lookup(unique_ids, client)

    except Exception as exc:
        logger.error(
            "DB query failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom logs",
        )

    logs = [_enrich_log(row, lookup) for row in rows]
    logger.info("Retrieved %d symptom logs for user %s", len(logs), user_id)
    return SymptomLogList(logs=logs, count=len(logs), limit=limit)


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
    client: SupabaseClient,
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

    try:
        start_dt = datetime(
            effective_start.year,
            effective_start.month,
            effective_start.day,
            tzinfo=timezone.utc,
        )
        end_dt = datetime(
            effective_end.year,
            effective_end.month,
            effective_end.day,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )
        response = (
            await client.table("symptom_logs")
            .select("symptoms")
            .eq("user_id", user_id)
            .gte("logged_at", start_dt.isoformat())
            .lte("logged_at", end_dt.isoformat())
            .execute()
        )
        rows = response.data or []
    except Exception as exc:
        logger.error(
            "DB query failed fetching logs for frequency stats (user %s): %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom statistics",
        )

    total_logs = len(rows)
    counts: Counter[str] = Counter(
        sid for row in rows for sid in (row.get("symptoms") or [])
    )

    if not counts:
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

    try:
        ref_response = (
            await client.table("symptoms_reference")
            .select("id, name, category")
            .in_("id", list(counts.keys()))
            .execute()
        )
        ref_rows = ref_response.data or []
    except Exception as exc:
        logger.error(
            "DB query failed fetching symptoms_reference for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom statistics",
        )

    ref_lookup = {row["id"]: row for row in ref_rows}

    stats: list[SymptomFrequency] = []
    for symptom_id, count in counts.most_common():
        ref = ref_lookup.get(symptom_id)
        if ref:
            stats.append(
                SymptomFrequency(
                    symptom_id=symptom_id,
                    symptom_name=ref["name"],
                    category=ref["category"],
                    count=count,
                )
            )
        else:
            # Data-integrity anomaly: log ID present in logs but not in reference
            logger.warning(
                "Symptom ID %s not found in symptoms_reference (data integrity issue)",
                symptom_id,
            )

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

# Maximum pairs returned — keeps the response manageable and the dashboard card
# readable.  All filtering (min_threshold) is applied first; we then take the
# top N by rate.
_MAX_PAIRS = 10


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
    client: SupabaseClient,
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

    # ------------------------------------------------------------------
    # 1. Fetch symptom arrays for the date range
    # ------------------------------------------------------------------
    try:
        start_dt = datetime(
            effective_start.year,
            effective_start.month,
            effective_start.day,
            tzinfo=timezone.utc,
        )
        end_dt = datetime(
            effective_end.year,
            effective_end.month,
            effective_end.day,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )
        response = (
            await client.table("symptom_logs")
            .select("symptoms")
            .eq("user_id", user_id)
            .gte("logged_at", start_dt.isoformat())
            .lte("logged_at", end_dt.isoformat())
            .execute()
        )
        rows = response.data or []
    except Exception as exc:
        logger.error(
            "DB query failed fetching logs for co-occurrence stats (user %s): %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom statistics",
        )

    total_logs = len(rows)
    logger.debug(
        "Co-occurrence: fetched %d logs for user %s range %s–%s",
        total_logs,
        user_id,
        effective_start,
        effective_end,
    )

    # ------------------------------------------------------------------
    # 2. Count individual symptom occurrences and pair co-occurrences
    # ------------------------------------------------------------------
    # symptom_counts[id] = number of logs that contain this symptom
    symptom_counts: Counter[str] = Counter()
    # pair_counts[(id_a, id_b)] = number of logs that contain both
    # Keys are always (min_id, max_id) to avoid double-counting.
    pair_counts: Counter[tuple[str, str]] = Counter()

    for row in rows:
        symptoms = row.get("symptoms") or []
        if not symptoms:
            continue
        unique_symptoms = list(dict.fromkeys(symptoms))  # deduplicate, preserve order
        for sid in unique_symptoms:
            symptom_counts[sid] += 1
        if len(unique_symptoms) >= 2:
            for a, b in itertools.combinations(sorted(unique_symptoms), 2):
                pair_counts[(a, b)] += 1

    logger.debug(
        "Co-occurrence: %d distinct symptoms, %d unique pairs found",
        len(symptom_counts),
        len(pair_counts),
    )

    # ------------------------------------------------------------------
    # 3. Filter by min_threshold and resolve names from symptoms_reference
    # ------------------------------------------------------------------
    qualifying = {
        pair: count
        for pair, count in pair_counts.items()
        if count >= min_threshold
    }

    if not qualifying:
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

    all_ids = {sid for pair in qualifying for sid in pair}
    try:
        ref_response = (
            await client.table("symptoms_reference")
            .select("id, name, category")
            .in_("id", list(all_ids))
            .execute()
        )
        ref_rows = ref_response.data or []
    except Exception as exc:
        logger.error(
            "DB query failed fetching symptoms_reference for co-occurrence (user %s): %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symptom statistics",
        )

    ref_lookup = {row["id"]: row for row in ref_rows}

    # ------------------------------------------------------------------
    # 4. Build pairs, calculate rates, sort and cap
    # ------------------------------------------------------------------
    pairs: list[SymptomPair] = []
    for (id_a, id_b), co_count in qualifying.items():
        ref_a = ref_lookup.get(id_a)
        ref_b = ref_lookup.get(id_b)
        if not ref_a or not ref_b:
            logger.warning(
                "Co-occurrence: symptom ID(s) missing from symptoms_reference "
                "(%s, %s) — skipping pair",
                id_a,
                id_b,
            )
            continue
        total_a = symptom_counts[id_a]
        rate = co_count / total_a if total_a else 0.0
        pairs.append(
            SymptomPair(
                symptom1_id=id_a,
                symptom1_name=ref_a["name"],
                symptom2_id=id_b,
                symptom2_name=ref_b["name"],
                cooccurrence_count=co_count,
                cooccurrence_rate=round(rate, 4),
                total_occurrences_symptom1=total_a,
            )
        )

    # Sort by rate descending; cap at _MAX_PAIRS
    pairs.sort(key=lambda p: p.cooccurrence_rate, reverse=True)
    pairs = pairs[:_MAX_PAIRS]

    logger.info(
        "Co-occurrence stats: user=%s range=%s–%s threshold=%d "
        "qualifying_pairs=%d returned=%d",
        user_id,
        effective_start,
        effective_end,
        min_threshold,
        len(qualifying),
        len(pairs),
    )
    return CooccurrenceStatsResponse(
        pairs=pairs,
        date_range_start=effective_start,
        date_range_end=effective_end,
        total_logs=total_logs,
        min_threshold=min_threshold,
    )
