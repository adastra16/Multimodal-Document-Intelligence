"""Trace ID is accepted, generated, and echoed on every response."""

from fastapi.testclient import TestClient

from app.core.middleware import TRACE_ID_HEADER


def test_health_echoes_incoming_trace_id(client: TestClient) -> None:
    response = client.get("/health", headers={TRACE_ID_HEADER: "trace-abc-123"})
    assert response.status_code == 200
    assert response.headers[TRACE_ID_HEADER] == "trace-abc-123"


def test_health_generates_trace_id_when_missing(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers[TRACE_ID_HEADER]
