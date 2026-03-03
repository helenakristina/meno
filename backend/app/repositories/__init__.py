"""Repository layer for data access.

Repositories handle all database queries for specific entities.
Each repository takes AsyncClient as a dependency and enforces user ownership.
"""

from app.repositories.user_repository import UserRepository

__all__ = ["UserRepository"]
