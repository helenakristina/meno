import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from supabase import AsyncClient

from app.core.supabase import get_client

logger = logging.getLogger(__name__)


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


CurrentUser = Annotated[str, Depends(get_current_user_id)]
