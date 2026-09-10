"""Integration coverage for grounded answer API output."""

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def _build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'data' / 'app.db').as_posix()}",
    )
    get_settings.cache_clear()
    return TestClient(create_app(settings))


def test_answer_endpoint_returns_cited_extractive_evidence(tmp_path: Path) -> None:
    pdf_path = tmp_path / "answer.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Revenue increased by ten percent in 2025.")
    pdf.save(pdf_path)
    pdf.close()

    with _build_client(tmp_path) as client:
        upload = client.post(
            "/documents",
            files=[("files", ("answer.pdf", pdf_path.read_bytes(), "application/pdf"))],
        )
        document_id = upload.json()["documents"][0]["document_id"]
        response = client.post(
            "/answers",
            json={"question": "What happened to revenue?", "document_id": document_id},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["generation_mode"] == "extractive"
    assert body["claims"]
    assert body["claims"][0]["citations"][0]["document_id"] == document_id
    assert body["claims"][0]["citations"][0]["page_numbers"] == [1]
    citation = body["claims"][0]["citations"][0]
    assert citation["filename"] == "answer.pdf"
    assert citation["regions"][0]["page_number"] == 1
    assert citation["regions"][0]["bbox"] is not None
