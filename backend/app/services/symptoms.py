import logging

from fastapi import HTTPException, status
from supabase import AsyncClient

logger = logging.getLogger(__name__)


async def validate_symptom_ids(symptom_ids: list[str], client: AsyncClient) -> None:
    """Validate that all symptom IDs exist in the symptoms_reference table.

    Deduplicates the input before querying so duplicate IDs in the request
    do not cause a false validation failure.

    Raises:
        HTTPException: 400 if any IDs are absent from symptoms_reference.
        HTTPException: 500 if the reference table query fails.
    """
    if not symptom_ids:
        return

    unique_ids = list(set(symptom_ids))

    try:
        result = (
            await client.table("symptoms_reference")
            .select("id")
            .in_("id", unique_ids)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to query symptoms_reference: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate symptom IDs",
        )

    if len(result.data) != len(unique_ids):
        valid_ids = {row["id"] for row in result.data}
        invalid_ids = sorted(set(unique_ids) - valid_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid symptom IDs: {invalid_ids}",
        )
