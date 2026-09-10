"""Document ingestion lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import BadRequestError, UnsupportedMediaTypeError
from app.models.document import DocumentRecord, DocumentStatus
from app.persistence.documents import DocumentRepository


class DocumentService:
    def __init__(self, settings: Settings, repository: DocumentRepository | None = None) -> None:
        self._settings = settings
        self._repository = repository or DocumentRepository(settings)

    def list_documents(self) -> list[DocumentRecord]:
        return self._repository.list_documents()

    def get_document(self, document_id: str) -> DocumentRecord:
        return self._repository.get_document(document_id)

    async def register_documents(self, files: Sequence[UploadFile]) -> list[DocumentRecord]:
        if not files:
            raise BadRequestError("At least one PDF must be uploaded")

        registered_documents: list[DocumentRecord] = []
        for file in files:
            registered_documents.append(await self._register_single_document(file))
        return registered_documents

    async def _register_single_document(self, file: UploadFile) -> DocumentRecord:
        filename = file.filename or "document.pdf"
        if not self._is_pdf(filename, file.content_type):
            raise UnsupportedMediaTypeError("Only PDF uploads are supported")

        document_id = str(uuid4())
        storage_path = self._repository.uploads_dir / f"{document_id}.pdf"
        file_bytes = await file.read()
        if len(file_bytes) > self._settings.max_upload_bytes:
            raise BadRequestError(
                f"Upload exceeds maximum size of {self._settings.max_upload_mb} MB"
            )

        storage_path.write_bytes(file_bytes)
        now = datetime.now(timezone.utc)
        document = DocumentRecord(
            document_id=document_id,
            filename=filename,
            content_type=file.content_type or "application/pdf",
            size_bytes=len(file_bytes),
            storage_path=str(storage_path),
            status=DocumentStatus.UPLOADED,
            page_count=None,
            created_at=now,
            updated_at=now,
        )
        return self._repository.insert(document)

    @staticmethod
    def _is_pdf(filename: str, content_type: str | None) -> bool:
        return filename.lower().endswith(".pdf") or content_type in {
            "application/pdf",
            "application/x-pdf",
        }