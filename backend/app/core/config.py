from typing import List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    APP_ENV: str = "development"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Anthropic
    ANTHROPIC_API_KEY: str

    # OpenAI (embeddings and LLM fallback)
    OPENAI_API_KEY: str = ""

    # LLM Provider selection (openai or anthropic)
    LLM_PROVIDER: str = "openai"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]


settings = Settings()
