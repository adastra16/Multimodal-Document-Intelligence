"""SQLite-backed chunk vector index."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from app.core.config import Settings
from app.models.document import ChunkType, DocumentChunk


class VectorIndexRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database_path = self._resolve_database_path(settings.database_url)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    page_numbers TEXT NOT NULL,
                    source_block_ids TEXT NOT NULL,
                    parent_chunk_id TEXT,
                    bbox TEXT,
                    chunk_metadata TEXT NOT NULL DEFAULT '{}',
                    embedding TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_document_id "
                "ON chunk_embeddings(document_id)"
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(chunk_embeddings)").fetchall()
            }
            missing_columns = {
                "parent_chunk_id": "TEXT",
                "bbox": "TEXT",
                "chunk_metadata": "TEXT NOT NULL DEFAULT '{}'",
            }
            for column, definition in missing_columns.items():
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE chunk_embeddings ADD COLUMN {column} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk_type "
                "ON chunk_embeddings(chunk_type)"
            )

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    def upsert_chunk(self, chunk: DocumentChunk, embedding: list[float]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chunk_embeddings (
                    chunk_id, document_id, chunk_type, text, page_numbers,
                    source_block_ids, parent_chunk_id, bbox, chunk_metadata, embedding,
                    embedding_dim, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    document_id = excluded.document_id,
                    chunk_type = excluded.chunk_type,
                    text = excluded.text,
                    page_numbers = excluded.page_numbers,
                    source_block_ids = excluded.source_block_ids,
                    parent_chunk_id = excluded.parent_chunk_id,
                    bbox = excluded.bbox,
                    chunk_metadata = excluded.chunk_metadata,
                    embedding = excluded.embedding,
                    embedding_dim = excluded.embedding_dim,
                    created_at = excluded.created_at
                """,
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.chunk_type.value,
                    chunk.text,
                    json.dumps(chunk.page_numbers),
                    json.dumps(chunk.source_block_ids),
                    chunk.parent_chunk_id,
                    json.dumps(chunk.bbox.model_dump()) if chunk.bbox is not None else None,
                    json.dumps(chunk.metadata),
                    json.dumps(embedding),
                    len(embedding),
                    self._serialize_datetime(datetime.now(timezone.utc)),
                ),
            )

    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        with self._connect() as connection:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                connection.execute(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id, document_id, chunk_type, text, page_numbers,
                        source_block_ids, parent_chunk_id, bbox, chunk_metadata, embedding,
                        embedding_dim, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        document_id = excluded.document_id,
                        chunk_type = excluded.chunk_type,
                        text = excluded.text,
                        page_numbers = excluded.page_numbers,
                        source_block_ids = excluded.source_block_ids,
                        parent_chunk_id = excluded.parent_chunk_id,
                        bbox = excluded.bbox,
                        chunk_metadata = excluded.chunk_metadata,
                        embedding = excluded.embedding,
                        embedding_dim = excluded.embedding_dim,
                        created_at = excluded.created_at
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.chunk_type.value,
                        chunk.text,
                        json.dumps(chunk.page_numbers),
                        json.dumps(chunk.source_block_ids),
                        chunk.parent_chunk_id,
                        json.dumps(chunk.bbox.model_dump()) if chunk.bbox is not None else None,
                        json.dumps(chunk.metadata),
                        json.dumps(embedding),
                        len(embedding),
                        self._serialize_datetime(datetime.now(timezone.utc)),
                    ),
                )

    def list_chunks(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunk_embeddings ORDER BY created_at DESC"
            ).fetchall()
        return [self._deserialize_row(row) for row in rows]

    def search(
        self,
        embedding: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[dict[str, object]]:
        candidates = self.list_chunks()
        scored: list[dict[str, object]] = []
        for candidate in candidates:
            if document_id is not None and candidate["document_id"] != document_id:
                continue
            candidate_embedding = candidate["embedding"]
            if not isinstance(candidate_embedding, list):
                continue
            score = self._cosine_similarity(embedding, candidate_embedding)
            scored.append({**candidate, "score": score})
        scored.sort(key=self._score_key, reverse=True)
        return scored[:limit]

    def get_chunk_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM chunk_embeddings").fetchone()
        return int(row["count"] if row is not None else 0)

    def has_chunk_type(self, document_id: str, chunk_type: ChunkType) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM chunk_embeddings WHERE document_id = ? AND chunk_type = ? LIMIT 1",
                (document_id, chunk_type.value),
            ).fetchone()
        return row is not None

    @staticmethod
    def _deserialize_row(row: sqlite3.Row) -> dict[str, object]:
        return {
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "chunk_type": ChunkType(row["chunk_type"]),
            "text": row["text"],
            "page_numbers": json.loads(row["page_numbers"]),
            "source_block_ids": json.loads(row["source_block_ids"]),
            "parent_chunk_id": row["parent_chunk_id"],
            "bbox": json.loads(row["bbox"]) if row["bbox"] is not None else None,
            "chunk_metadata": json.loads(row["chunk_metadata"]),
            "embedding": json.loads(row["embedding"]),
            "embedding_dim": row["embedding_dim"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        return sum(left[index] * right[index] for index in range(min(len(left), len(right))))

    @staticmethod
    def _score_key(item: dict[str, object]) -> float:
        return cast(float, item["score"])
