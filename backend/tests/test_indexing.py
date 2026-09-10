"""Integration coverage for indexing parsed documents into the vector store."""

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.persistence.vector_index import VectorIndexRepository


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
    page_one.insert_text((72, 72), "Alpha chunk text\nShared claim", fontsize=12)
    page_two = document.new_page(width=595, height=842)
    page_two.insert_text((72, 72), "Beta chunk text\nCross-page detail", fontsize=12)
    document.save(path)
    document.close()


def test_uploaded_document_populates_vector_index(tmp_path: Path) -> None:
    pdf_path = tmp_path / "indexed.pdf"
    _create_pdf(pdf_path)

    with _build_client(tmp_path) as client:
        response = client.post(
            "/documents",
            files=[("files", ("indexed.pdf", pdf_path.read_bytes(), "application/pdf"))],
        )

    assert response.status_code == 200
    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'data' / 'app.db').as_posix()}",
    )
    repository = VectorIndexRepository(settings)
    assert repository.get_chunk_count() >= 3
    indexed_chunks = repository.list_chunks()
    bridge_chunk = next(
        chunk for chunk in indexed_chunks if chunk["chunk_type"].value == "cross_page"
    )
    assert bridge_chunk["parent_chunk_id"] is not None

    query_results = repository.search(
        indexed_chunks[0]["embedding"],
        limit=1,
    )
    assert query_results

    with _build_client(tmp_path) as client:
        document_id = response.json()["documents"][0]["document_id"]
        detail = client.get(f"/documents/{document_id}").json()

    assert len(detail["chunks"]) >= 3
