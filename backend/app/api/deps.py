"""FastAPI dependencies. Route handlers should take these instead of importing globals."""

from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    return get_settings()
