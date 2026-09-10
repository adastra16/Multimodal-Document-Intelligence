"""Health endpoint and health service contracts."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.health import get_health_status


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert "env" in body


def test_health_service_uses_settings_env() -> None:
    settings = Settings(app_env="test")
    status = get_health_status(settings)
    assert status.status == "ok"
    assert status.env == "test"
