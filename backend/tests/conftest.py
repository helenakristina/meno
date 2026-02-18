"""Root conftest: set dummy env vars BEFORE any app module is imported.

pydantic-settings validates required fields at import time, so these must
be set here — at the module level, before any `from app.*` import.
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
