"""Health status for the process. No I/O yet; later phases can add dependency checks."""

from app import __version__
from app.core.config import Settings
from app.models.health import HealthStatus


def get_health_status(settings: Settings) -> HealthStatus:
    return HealthStatus(status="ok", version=__version__, env=settings.app_env)
