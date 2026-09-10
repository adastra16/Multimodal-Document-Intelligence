"""Unit coverage for structure-aware chunk building."""

from datetime import datetime, timezone

from app.ingestion.chunking import ChunkingConfig, StructureAwareChunker
from app.models.document import (
    BlockType,
    BoundingBox,
    DocumentBlock,
    DocumentPage,
    DocumentRecord,
    DocumentStatus,
)


def _document_with_pages() -> DocumentRecord:
    page_one = DocumentPage(
        page_number=1,
        width=600,
        height=800,
        blocks=[
            DocumentBlock(
                block_id="doc-p1-b1",
                page_number=1,
                block_type=BlockType.TEXT,
                text="Alpha heading",
                bbox=BoundingBox(x0=10, y0=10, x1=200, y1=40),
            ),
            DocumentBlock(
                block_id="doc-p1-b2",
                page_number=1,
                block_type=BlockType.TEXT,
                text="Alpha detail",
                bbox=BoundingBox(x0=10, y0=50, x1=200, y1=90),
            ),
            DocumentBlock(
                block_id="doc-p1-b3",
                page_number=1,
                block_type=BlockType.TEXT,
                text="Alpha conclusion",
                bbox=BoundingBox(x0=10, y0=100, x1=200, y1=140),
            ),
        ],
    )
    page_two = DocumentPage(
        page_number=2,
        width=600,
        height=800,
        blocks=[
            DocumentBlock(
                block_id="doc-p2-b1",
                page_number=2,
                block_type=BlockType.TEXT,
                text="Beta intro",
                bbox=BoundingBox(x0=10, y0=10, x1=200, y1=40),
            ),
            DocumentBlock(
                block_id="doc-p2-b2",
                page_number=2,
                block_type=BlockType.TEXT,
                text="Beta evidence",
                bbox=BoundingBox(x0=10, y0=50, x1=200, y1=90),
            ),
        ],
    )
    return DocumentRecord(
        document_id="doc-structure",
        filename="structure.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_path="/tmp/structure.pdf",
        status=DocumentStatus.READY,
        page_count=2,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        pages=[page_one, page_two],
    )


def test_structure_aware_chunker_builds_page_windows_and_bridges() -> None:
    chunker = StructureAwareChunker(
        ChunkingConfig(window_size=3, window_step=2, bridge_block_count=1)
    )
    chunks = chunker.build(_document_with_pages())

    page_chunks = [chunk for chunk in chunks if chunk.chunk_type.value == "page"]
    window_chunks = [chunk for chunk in chunks if chunk.chunk_type.value == "window"]
    bridge_chunks = [chunk for chunk in chunks if chunk.chunk_type.value == "cross_page"]

    assert len(page_chunks) == 2
    assert window_chunks
    assert len(bridge_chunks) == 1
    assert page_chunks[0].child_chunk_ids
    assert bridge_chunks[0].parent_chunk_id == page_chunks[0].chunk_id
    assert bridge_chunks[0].page_numbers == [1, 2]
    assert "Alpha conclusion" in bridge_chunks[0].text
    assert "Beta intro" in bridge_chunks[0].text