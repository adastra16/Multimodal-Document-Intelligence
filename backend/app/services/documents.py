"""Document ingestion lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    DependencyUnavailableError,
    IndexingError,
    UnsupportedMediaTypeError,
)
from app.ingestion.pdf_parser import PdfDocumentParser
from app.models.document import DocumentRecord, DocumentStatus
from app.persistence.documents import DocumentRepository
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.indexing import DocumentIndexer


class DocumentService:
    def __init__(self, settings: Settings, repository: DocumentRepository | None = None) -> None:
        self._settings = settings
        self._repository = repository or DocumentRepository(settings)
        self._vector_index = VectorIndexRepository(settings)
        self._indexer = DocumentIndexer(
            self._vector_index,
            HashedEmbeddingModel(self._settings.embedding_dimensions),
        )
        self._parser = PdfDocumentParser()

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

    def ingest_file(self, file_path: Path, filename: str | None = None) -> DocumentRecord:
        resolved_filename = filename or file_path.name
        file_bytes = file_path.read_bytes()
        return self.ingest_bytes(file_bytes, resolved_filename)

    def ingest_bytes(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        content_type: str = "application/pdf",
    ) -> DocumentRecord:
        if not self._is_pdf(filename, content_type):
            raise UnsupportedMediaTypeError("Only PDF uploads are supported")
        if len(file_bytes) > self._settings.max_upload_bytes:
            raise BadRequestError(
                f"Upload exceeds maximum size of {self._settings.max_upload_mb} MB"
            )

        document_id = str(uuid4())
        storage_path = self._repository.uploads_dir / f"{document_id}.pdf"
        storage_path.write_bytes(file_bytes)
        now = datetime.now(timezone.utc)
        document = DocumentRecord(
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
            storage_path=str(storage_path),
            status=DocumentStatus.PROCESSING,
            page_count=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.insert(document)

        try:
            parsed_document = self._parser.parse(document)
        except (BadRequestError, DependencyUnavailableError):
            self._repository.update_status(document_id, DocumentStatus.FAILED)
            raise

        self._repository.save_artifact(parsed_document)
        try:
            self._indexer.index(parsed_document)
        except Exception as exc:  # pragma: no cover - defensive failure path
            self._repository.update_status(document_id, DocumentStatus.FAILED)
            raise IndexingError("Unable to index parsed chunks") from exc

        self._repository.update_status(
            document_id,
            DocumentStatus.READY,
            page_count=parsed_document.page_count,
        )
        return self._repository.get_document(document_id)

    async def _register_single_document(self, file: UploadFile) -> DocumentRecord:
        filename = file.filename or "document.pdf"
        file_bytes = await file.read()
        return self.ingest_bytes(file_bytes, filename, file.content_type or "application/pdf")


    @staticmethod
    def _is_pdf(filename: str, content_type: str | None) -> bool:
        return filename.lower().endswith(".pdf") or content_type in {
            "application/pdf",
            "application/x-pdf",
        }