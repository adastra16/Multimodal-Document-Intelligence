"""Liveness endpoint used by operators and later by Docker Compose."""

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.api.schemas import HealthResponse
from app.core.config import Settings
from app.services.health import get_health_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    status = get_health_status(settings)
    return HealthResponse(status=status.status, version=status.version, env=status.env)
