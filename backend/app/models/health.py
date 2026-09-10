"""Domain health status, independent of HTTP."""

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    version: str
    env: str
