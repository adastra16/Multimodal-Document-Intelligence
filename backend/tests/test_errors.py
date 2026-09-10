"""Typed error envelope and leak-safe unexpected errors."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.middleware import TRACE_ID_HEADER
from app.main import create_app


def test_app_error_returns_typed_envelope() -> None:
    get_settings.cache_clear()
    app = create_app()

    @app.get("/__not-found")
    def missing() -> None:
        raise NotFoundError("Document missing")

    with TestClient(app) as client:
        response = client.get("/__not-found", headers={TRACE_ID_HEADER: "err-trace"})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Document missing"
    assert body["error"]["trace_id"] == "err-trace"
    assert response.headers[TRACE_ID_HEADER] == "err-trace"


def test_unhandled_error_does_not_leak_details() -> None:
    get_settings.cache_clear()
    app = create_app()

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret internals" not in response.text
    assert body["error"]["trace_id"]
