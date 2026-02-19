import logging
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import AsyncClient

from app.core.supabase import get_client
from app.models.symptoms import (
    SymptomDetail,
    SymptomLogCreate,
    SymptomLogList,
    SymptomLogResponse,
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
