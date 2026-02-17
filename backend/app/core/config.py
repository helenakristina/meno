from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Anthropic
    ANTHROPIC_API_KEY: str

    # OpenAI (embeddings)
    OPENAI_API_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
