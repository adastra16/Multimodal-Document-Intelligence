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
    ForbiddenError,
    IndexingError,
    UnsupportedMediaTypeError,
)
from app.ingestion.ocr import TesseractOcrEngine
from app.ingestion.pdf_parser import PdfDocumentParser
from app.models.document import DocumentOrigin, DocumentRecord, DocumentStatus
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
        self._parser = PdfDocumentParser(
            ocr_engine=TesseractOcrEngine(
                command=self._settings.ocr_command,
                language=self._settings.ocr_language,
                dpi=self._settings.ocr_dpi,
            )
        )

    def list_documents(self, origin: DocumentOrigin | None = None) -> list[DocumentRecord]:
        return self._repository.list_documents(origin)

    def list_uploaded_documents(self) -> list[DocumentRecord]:
        return self._repository.list_documents(DocumentOrigin.USER_UPLOAD)

    def get_document(self, document_id: str) -> DocumentRecord:
        return self._repository.get_document(document_id)

    def get_uploaded_document(self, document_id: str) -> DocumentRecord:
        document = self.get_document(document_id)
        if document.origin != DocumentOrigin.USER_UPLOAD:
            raise ForbiddenError("Evaluation documents are not available through the upload UI")
        return document

    def delete_uploaded_document(self, document_id: str) -> None:
        document = self.get_uploaded_document(document_id)
        self._vector_index.delete_document_chunks(document.document_id)
        self._repository.delete(document)

    async def register_documents(self, files: Sequence[UploadFile]) -> list[DocumentRecord]:
        if not files:
            raise BadRequestError("At least one PDF must be uploaded")

        registered_documents: list[DocumentRecord] = []
        for file in files:
            registered_documents.append(await self._register_single_document(file))
        return registered_documents

    def ingest_file(
        self,
        file_path: Path,
        filename: str | None = None,
        origin: DocumentOrigin = DocumentOrigin.EVALUATION,
    ) -> DocumentRecord:
        resolved_filename = filename or file_path.name
        file_bytes = file_path.read_bytes()
        return self.ingest_bytes(file_bytes, resolved_filename, origin=origin)

    def prepare_evaluation_documents(self, filenames: set[str]) -> None:
        """Classify benchmark fixtures created by earlier versions as internal data."""
        self._repository.mark_filenames_as_evaluation(filenames)
        self._vector_index.delete_legacy_block_chunks()

    def refresh_evaluation_document(self, file_path: Path, filename: str) -> DocumentRecord:
        """Re-parse an evaluation fixture so its artifact and index match the active code."""
        existing = [
            document
            for document in self._repository.list_documents(DocumentOrigin.EVALUATION)
            if document.filename == filename
        ]
        if not existing:
            return self.ingest_file(file_path, filename, origin=DocumentOrigin.EVALUATION)

        document = existing[0]
        for duplicate in existing[1:]:
            self._vector_index.delete_document_chunks(duplicate.document_id)
            self._repository.delete(duplicate)

        Path(document.storage_path).write_bytes(file_path.read_bytes())
        self._repository.delete_artifact(document.document_id)
        self._repository.update_status(document.document_id, DocumentStatus.PROCESSING)
        self._vector_index.delete_document_chunks(document.document_id)
        parsed_document = self._parser.parse(document)
        self._repository.save_artifact(parsed_document)
        self._indexer.index(parsed_document)
        self._repository.update_status(
            document.document_id,
            DocumentStatus.READY,
            page_count=parsed_document.page_count,
        )
        return self._repository.get_document(document.document_id)

    def ingest_bytes(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        content_type: str = "application/pdf",
        origin: DocumentOrigin = DocumentOrigin.USER_UPLOAD,
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
            origin=origin,
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
