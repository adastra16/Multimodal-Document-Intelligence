"""Document upload and lookup integration coverage."""

from pathlib import Path

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


def test_upload_list_and_get_document(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.post(
            "/documents",
            files=[("files", ("sample.pdf", b"%PDF-1.4 sample", "application/pdf"))],
        )

        assert response.status_code == 200
        uploaded = response.json()["documents"]
        assert len(uploaded) == 1
        document_id = uploaded[0]["document_id"]
        assert uploaded[0]["filename"] == "sample.pdf"
        assert uploaded[0]["status"] == "uploaded"

        list_response = client.get("/documents")
        assert list_response.status_code == 200
        listed = list_response.json()["documents"]
        assert len(listed) == 1
        assert listed[0]["document_id"] == document_id

        detail_response = client.get(f"/documents/{document_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["document_id"] == document_id


def test_rejects_non_pdf_upload(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.post(
            "/documents",
            files=[("files", ("sample.txt", b"not a pdf", "text/plain"))],
        )

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "unsupported_media_type"