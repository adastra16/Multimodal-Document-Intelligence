"""Integration coverage for the hybrid retrieval API endpoint."""

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


def _create_pdf(path: Path) -> None:
    document = fitz.open()
    page_one = document.new_page(width=595, height=842)
    page_one.insert_text((72, 72), "Alpha shared claim on page one", fontsize=12)
    page_two = document.new_page(width=595, height=842)
    page_two.insert_text((72, 72), "Beta supporting detail on page two", fontsize=12)
    document.save(path)
    document.close()


def test_retrieval_endpoint_returns_ranked_matches(tmp_path: Path) -> None:
    pdf_path = tmp_path / "retrieval.pdf"
    _create_pdf(pdf_path)

    with _build_client(tmp_path) as client:
        upload_response = client.post(
            "/documents",
            files=[("files", ("retrieval.pdf", pdf_path.read_bytes(), "application/pdf"))],
        )
        document_id = upload_response.json()["documents"][0]["document_id"]

        response = client.post(
            "/retrieval/search",
            json={"query": "shared claim", "limit": 3, "document_id": document_id},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "shared claim"
    assert body["result_count"] >= 1
    top_result = body["results"][0]
    assert top_result["document_id"] == document_id
    assert top_result["hybrid_score"] >= top_result["lexical_score"] * 0.25
    assert top_result["page_numbers"]
    assert top_result["retrieval_stage"] == "reranked"
    assert body["evidence_groups"]
    evidence_group = body["evidence_groups"][0]
    assert evidence_group["anchor_chunk_id"] == top_result["chunk_id"]
    assert evidence_group["hits"][0]["metadata"]["evidence_role"] == "anchor"
