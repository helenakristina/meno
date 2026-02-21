from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, export, symptoms, users
from app.core.config import settings
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
app = FastAPI(
    title="Meno API",
    description="Backend API for the Meno app",
    version="0.1.0",
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meno-api"}
