from supabase import AsyncClient, acreate_client

from app.core.config import settings

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        # Service role key bypasses RLS; endpoints enforce user isolation
        # by always filtering queries on the authenticated user_id.
        _client = await acreate_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )
    return _client
