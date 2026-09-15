"""Structure-aware chunk building for parsed document artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.document import (
    BoundingBox,
    ChunkType,
    DocumentBlock,
    DocumentChunk,
    DocumentPage,
    DocumentRecord,
)


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for chunk boundaries and cross-page bridges."""

    window_size: int = 3
    window_step: int = 2
    bridge_block_count: int = 1


class StructureAwareChunker:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()

    def build(self, document: DocumentRecord) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        page_chunks: list[DocumentChunk] = []
        page_units: list[list[DocumentBlock]] = []

        for page in sorted(document.pages, key=lambda page: page.page_number):
            text_units = self._text_blocks(page)
            page_units.append(text_units)
            page_chunk = self._build_page_chunk(document.document_id, page, text_units)
            page_chunks.append(page_chunk)
            chunks.append(page_chunk)

            block_chunks = self._build_block_chunks(document.document_id, page, text_units)
            page_chunk.child_chunk_ids.extend(chunk.chunk_id for chunk in block_chunks)
            chunks.extend(block_chunks)

            window_chunks = self._build_window_chunks(document.document_id, page, text_units)
            page_chunk.child_chunk_ids.extend(chunk.chunk_id for chunk in window_chunks)
            chunks.extend(window_chunks)

        bridge_chunks = self._build_bridge_chunks(document.document_id, page_chunks, page_units)
        chunks.extend(bridge_chunks)
        return chunks

    def _build_page_chunk(
        self,
        document_id: str,
        page: DocumentPage,
        text_units: list[DocumentBlock],
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=f"{document_id}-page-{page.page_number}",
            document_id=document_id,
            chunk_type=ChunkType.PAGE,
            text=self._join_text(text_units),
            page_numbers=[page.page_number],
            source_block_ids=[unit.block_id for unit in text_units],
            bbox=self._merge_bbox(unit.bbox for unit in text_units),
            metadata={
                "chunking_strategy": "page",
                "text_unit_count": len(text_units),
            },
        )

    def _build_window_chunks(
        self,
        document_id: str,
        page: DocumentPage,
        text_units: list[DocumentBlock],
    ) -> list[DocumentChunk]:
        if len(text_units) < 2:
            return []

        chunks: list[DocumentChunk] = []
        for start in range(0, len(text_units), self._config.window_step):
            end = min(start + self._config.window_size, len(text_units))
            window = text_units[start:end]
            if len(window) < 2:
                continue
            chunk_id = f"{document_id}-page-{page.page_number}-window-{start}-{end}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_type=ChunkType.WINDOW,
                    text=self._join_text(window),
                    page_numbers=[page.page_number],
                    parent_chunk_id=f"{document_id}-page-{page.page_number}",
                    source_block_ids=[unit.block_id for unit in window],
                    bbox=self._merge_bbox(unit.bbox for unit in window),
                    metadata={
                        "chunking_strategy": "window",
                        "start_index": start,
                        "end_index": end,
                    },
                )
            )
        return chunks

    def _build_bridge_chunks(
        self,
        document_id: str,
        page_chunks: list[DocumentChunk],
        page_units: list[list[DocumentBlock]],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for index in range(len(page_chunks) - 1):
            left_page = page_chunks[index]
            right_page = page_chunks[index + 1]
            left_units = page_units[index][-self._config.bridge_block_count :]
            right_units = page_units[index + 1][: self._config.bridge_block_count]
            combined_units = [*left_units, *right_units]
            if not combined_units:
                continue
            bridge_id = (
                f"{document_id}-bridge-{left_page.page_numbers[0]}-"
                f"{right_page.page_numbers[0]}"
            )
            bridge_chunk = DocumentChunk(
                chunk_id=bridge_id,
                document_id=document_id,
                chunk_type=ChunkType.CROSS_PAGE,
                text=self._join_text(combined_units),
                page_numbers=[left_page.page_numbers[0], right_page.page_numbers[0]],
                parent_chunk_id=left_page.chunk_id,
                source_block_ids=[unit.block_id for unit in combined_units],
                bbox=self._merge_bbox(unit.bbox for unit in combined_units),
                metadata={
                    "chunking_strategy": "cross_page_bridge",
                    "left_page": left_page.page_numbers[0],
                    "right_page": right_page.page_numbers[0],
                },
            )
            left_page.child_chunk_ids.append(bridge_chunk.chunk_id)
            right_page.child_chunk_ids.append(bridge_chunk.chunk_id)
            chunks.append(bridge_chunk)
        return chunks

    @staticmethod
    def _text_blocks(page: DocumentPage) -> list[DocumentBlock]:
        return [block for block in page.blocks if block.text and block.text.strip()]

    @staticmethod
    def _join_text(units: Iterable[DocumentBlock]) -> str:
        return "\n".join(
            unit.text.strip() for unit in units if unit.text and unit.text.strip()
        ).strip()

    @staticmethod
    def _merge_bbox(bboxes: Iterable[BoundingBox | None]) -> BoundingBox | None:
        concrete = [bbox for bbox in bboxes if bbox is not None]
        if not concrete:
            return None
        return BoundingBox(
            x0=min(bbox.x0 for bbox in concrete),
            y0=min(bbox.y0 for bbox in concrete),
            x1=max(bbox.x1 for bbox in concrete),
            y1=max(bbox.y1 for bbox in concrete),
        )

    @staticmethod
    def _build_block_chunks(
        document_id: str,
        page: DocumentPage,
        text_units: list[DocumentBlock],
    ) -> list[DocumentChunk]:
        page_chunk_id = f"{document_id}-page-{page.page_number}"
        return [
            DocumentChunk(
                chunk_id=f"{block.block_id}-chunk",
                document_id=document_id,
                chunk_type=ChunkType.BLOCK,
                text=block.text.strip(),
                page_numbers=[block.page_number],
                parent_chunk_id=page_chunk_id,
                source_block_ids=[block.block_id],
                bbox=block.bbox,
                metadata={
                    "chunking_strategy": "document_block",
                    "block_type": block.block_type.value,
                    "reading_order": block.reading_order,
                    "section_title": block.section_title,
                },
            )
            for block in text_units
            if block.text and block.text.strip()
        ]
