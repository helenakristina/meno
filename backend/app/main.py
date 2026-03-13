from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.routes import appointment, chat, export, providers, symptoms, users
from app.core.config import settings
from app.exceptions import (
    MenoBaseError,
    EntityNotFoundError,
    DatabaseError,
    ValidationError,
    UnauthorizedError,
    PermissionError,
    DuplicateEntityError,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Meno API",
    description="Backend API for the Meno app",
    version="0.1.0",
)


# Global exception handlers - convert domain exceptions to HTTP responses
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    """Convert EntityNotFoundError to 404 response."""
    logger.info("EntityNotFoundError: %s", exc)
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    """Convert DatabaseError to 500 response."""
    logger.error("DatabaseError: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred"},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Convert ValidationError to 400 response."""
    logger.info("ValidationError: %s", exc)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_error_handler(request: Request, exc: UnauthorizedError):
    """Convert UnauthorizedError to 401 response."""
    logger.warning("UnauthorizedError: %s", exc)
    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized"},
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    """Convert PermissionError to 403 response."""
    logger.warning("PermissionError: %s", exc)
    return JSONResponse(
        status_code=403,
        content={"detail": "Forbidden"},
    )


@app.exception_handler(DuplicateEntityError)
async def duplicate_entity_handler(request: Request, exc: DuplicateEntityError):
    """Convert DuplicateEntityError to 409 response."""
    logger.info("DuplicateEntityError: %s", exc)
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(symptoms.router)
app.include_router(users.router)
app.include_router(export.router)
app.include_router(chat.router)
app.include_router(providers.router)
app.include_router(appointment.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meno-api"}
