"""SQLite-backed persistence for document metadata."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.document import DocumentRecord, DocumentStatus


class DocumentRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database_path = self._resolve_database_path(settings.database_url)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._uploads_dir = self._settings.data_dir / "uploads"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts_dir = self._settings.data_dir / "artifacts"
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @staticmethod
    def _resolve_database_path(database_url: str) -> Path:
        if database_url.startswith("sqlite:///"):
            return Path(database_url.removeprefix("sqlite:///"))
        if database_url.startswith("sqlite://"):
            return Path(database_url.removeprefix("sqlite://"))
        return Path(database_url)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_status_created_at "
                "ON documents(status, created_at DESC)"
            )

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _deserialize_row(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            document_id=row["document_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            storage_path=row["storage_path"],
            status=DocumentStatus(row["status"]),
            page_count=row["page_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def insert(self, document: DocumentRecord) -> DocumentRecord:
        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO documents (
                        document_id, filename, content_type, size_bytes, storage_path,
                        status, page_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document.document_id,
                        document.filename,
                        document.content_type,
                        document.size_bytes,
                        document.storage_path,
                        document.status.value,
                        document.page_count,
                        self._serialize_datetime(document.created_at),
                        self._serialize_datetime(document.updated_at),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Document {document.document_id} already exists") from exc
        return document

    def list_documents(self) -> list[DocumentRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [self._deserialize_row(row) for row in rows]

    def get_document(self, document_id: str) -> DocumentRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Document {document_id} not found")
        artifact = self._load_artifact(document_id)
        return artifact or self._deserialize_row(row)

    def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        page_count: int | None = None,
    ) -> DocumentRecord:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE documents
                SET status = ?, page_count = COALESCE(?, page_count), updated_at = ?
                WHERE document_id = ?
                """,
                (status.value, page_count, self._serialize_datetime(now), document_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError(f"Document {document_id} not found")
        return self.get_document(document_id)

    def save_artifact(self, document: DocumentRecord) -> DocumentRecord:
        self._artifact_path(document.document_id).write_text(
            document.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )
        return document

    @property
    def uploads_dir(self) -> Path:
        return self._uploads_dir

    @property
    def artifacts_dir(self) -> Path:
        return self._artifacts_dir

    def _artifact_path(self, document_id: str) -> Path:
        return self._artifacts_dir / f"{document_id}.json"

    def _load_artifact(self, document_id: str) -> DocumentRecord | None:
        artifact_path = self._artifact_path(document_id)
        if not artifact_path.exists():
            return None
        return DocumentRecord.model_validate_json(artifact_path.read_text(encoding="utf-8"))
