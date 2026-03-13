"""Domain exceptions for Meno backend.

These exceptions represent business logic and data layer errors.
They should be raised by repositories and services.
Routes and global exception handlers convert these to HTTP responses.

This separation keeps repositories, services, and background jobs
independent of HTTP semantics.
"""


class MenoBaseError(Exception):
    """Base exception for all Meno domain errors."""

    pass


class EntityNotFoundError(MenoBaseError):
    """Entity doesn't exist or doesn't belong to authenticated user.

    Raised when:
    - User requests resource they don't own
    - Resource ID doesn't exist in database
    - Query returns no results

    HTTP Mapping: 404 Not Found
    """

    pass


class DatabaseError(MenoBaseError):
    """Database operation failed (connection, query error, constraint violation).

    Raised when:
    - Supabase connection fails
    - Query execution fails
    - Data constraint is violated
    - Transaction fails

    HTTP Mapping: 500 Internal Server Error
    """

    pass


class ValidationError(MenoBaseError):
    """Input validation failed (invalid enum, constraint, business rule).

    Raised when:
    - Pydantic model validation fails at service level
    - Business rule constraint is violated (e.g., concern list empty)
    - Data doesn't meet application requirements

    HTTP Mapping: 400 Bad Request
    """

    pass


class UnauthorizedError(MenoBaseError):
    """User is not authenticated or token is invalid.

    Raised when:
    - User tries to access resource without auth
    - Auth token is expired or invalid

    HTTP Mapping: 401 Unauthorized

    Note: Usually FastAPI's Depends(CurrentUser) handles this,
    but services might raise this for additional auth checks.
    """

    pass


class PermissionError(MenoBaseError):
    """User is authenticated but not authorized for this operation.

    Raised when:
    - User tries to modify another user's data
    - User doesn't have required role/permission

    HTTP Mapping: 403 Forbidden

    Note: RLS policies should prevent most cases, but services
    might add additional permission checks.
    """

    pass


class DuplicateEntityError(MenoBaseError):
    """Entity already exists (e.g., duplicate shortlist entry, duplicate user).

    Raised when:
    - Attempting to create a resource that already exists
    - Unique constraint would be violated

    HTTP Mapping: 409 Conflict
    """

    pass
