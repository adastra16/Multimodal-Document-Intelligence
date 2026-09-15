"""Integration coverage for block-level retrieval and legacy-index backfill."""

from datetime import datetime, timezone

from app.core.config import Settings
from app.ingestion.chunking import StructureAwareChunker
from app.models.document import (
    BlockType,
    BoundingBox,
    ChunkType,
    DocumentBlock,
    DocumentPage,
    DocumentRecord,
    DocumentStatus,
)
from app.persistence.documents import DocumentRepository
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.indexing import DocumentIndexer
from app.services.retrieval import RetrievalService


def test_retrieval_backfills_and_returns_precise_block_evidence(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'data' / 'app.db').as_posix()}",
    )
    now = datetime.now(timezone.utc)
    document = DocumentRecord(
        document_id="doc-blocks",
        filename="blocks.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_path=str(tmp_path / "blocks.pdf"),
        status=DocumentStatus.READY,
        page_count=1,
        created_at=now,
        updated_at=now,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="doc-blocks-p1-b1",
                        page_number=1,
                        block_type=BlockType.TEXT,
                        text="General background about machine learning.",
                        bbox=BoundingBox(x0=10, y0=10, x1=200, y1=40),
                    ),
                    DocumentBlock(
                        block_id="doc-blocks-p1-b2",
                        page_number=1,
                        block_type=BlockType.TABLE,
                        text="Rare metric: 93.2 exact answer.",
                        bbox=BoundingBox(x0=10, y0=50, x1=200, y1=90),
                    ),
                ],
            )
        ],
    )
    chunker = StructureAwareChunker()
    legacy_document = document.model_copy(
        update={
            "chunks": [
                chunk
                for chunk in chunker.build(document)
                if chunk.chunk_type != ChunkType.BLOCK
            ]
        }
    )
    document_repository = DocumentRepository(settings)
    document_repository.insert(legacy_document)
    document_repository.save_artifact(legacy_document)
    vector_repository = VectorIndexRepository(settings)
    DocumentIndexer(vector_repository, HashedEmbeddingModel(settings.embedding_dimensions)).index(
        legacy_document
    )

    result = RetrievalService(
        settings,
        repository=vector_repository,
        document_repository=document_repository,
    ).search("rare metric 93.2 exact answer", document_id=document.document_id)

    block_hit = next(hit for hit in result.results if hit.chunk_type == ChunkType.BLOCK)
    assert block_hit.source_block_ids == ["doc-blocks-p1-b2"]
    assert block_hit.metadata["parent_chunk_id"] == "doc-blocks-page-1"
    assert block_hit.metadata["block_type"] == "table"
    assert block_hit.metadata["bbox"] == {"x0": 10.0, "y0": 50.0, "x1": 200.0, "y1": 90.0}
    assert vector_repository.has_chunk_type(document.document_id, ChunkType.BLOCK)
    assert any(
        chunk.chunk_type == ChunkType.BLOCK
        for chunk in document_repository.get_document(document.document_id).chunks
    )
