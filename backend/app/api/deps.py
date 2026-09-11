"""FastAPI dependencies. Route handlers should take these instead of importing globals."""

from typing import cast

from fastapi import Request

from app.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)
