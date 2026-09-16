"""Document upload and lookup integration coverage."""

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.document import DocumentOrigin
from app.services.documents import DocumentService


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
    page_one.insert_text((72, 72), "Alpha section\nShared conclusion", fontsize=12)
    page_two = document.new_page(width=595, height=842)
    page_two.insert_text((72, 72), "Beta section\nCross-page evidence", fontsize=12)
    document.save(path)
    document.close()


def test_upload_list_and_get_document(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path)

    with _build_client(tmp_path) as client:
        response = client.post(
            "/documents",
            files=[("files", ("sample.pdf", pdf_path.read_bytes(), "application/pdf"))],
        )

        assert response.status_code == 200
        uploaded = response.json()["documents"]
        assert len(uploaded) == 1
        document_id = uploaded[0]["document_id"]
        assert uploaded[0]["filename"] == "sample.pdf"
        assert uploaded[0]["status"] == "ready"
        assert uploaded[0]["page_count"] == 2

        list_response = client.get("/documents")
        assert list_response.status_code == 200
        listed = list_response.json()["documents"]
        assert len(listed) == 1
        assert listed[0]["document_id"] == document_id
        assert listed[0]["status"] == "ready"

        detail_response = client.get(f"/documents/{document_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["document_id"] == document_id
        assert detail["page_count"] == 2
        assert detail["pages"][0]["page_number"] == 1
        assert detail["pages"][0]["blocks"][0]["block_type"] == "text"

        file_response = client.get(f"/documents/{document_id}/file")
        assert file_response.status_code == 200
        assert file_response.headers["content-type"] == "application/pdf"
        assert file_response.content.startswith(b"%PDF")


def test_rejects_non_pdf_upload(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.post(
            "/documents",
            files=[("files", ("sample.txt", b"not a pdf", "text/plain"))],
        )

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "unsupported_media_type"


def test_list_excludes_evaluation_documents_and_delete_removes_upload_data(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _create_pdf(pdf_path)
    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'data' / 'app.db').as_posix()}",
    )
    with _build_client(tmp_path) as client:
        upload = client.post(
            "/documents",
            files=[("files", ("sample.pdf", pdf_path.read_bytes(), "application/pdf"))],
        )
        document_id = upload.json()["documents"][0]["document_id"]
        evaluation = DocumentService(settings).ingest_file(pdf_path, "benchmark.pdf")

        listed = client.get("/documents")
        assert [item["document_id"] for item in listed.json()["documents"]] == [document_id]
        assert evaluation.origin == DocumentOrigin.EVALUATION

        delete_response = client.delete(f"/documents/{document_id}")
        assert delete_response.status_code == 204
        assert client.get("/documents").json()["documents"] == []
        assert client.get(f"/documents/{document_id}").status_code == 404
        assert client.delete(f"/documents/{evaluation.document_id}").status_code == 403
