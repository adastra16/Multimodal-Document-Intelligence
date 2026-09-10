"""PDF parsing into the canonical internal document representation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fitz  # type: ignore[import-not-found, import-untyped]
except ImportError:  # pragma: no cover - exercised when the dependency is missing
    fitz = None

from app.core.errors import BadRequestError, DependencyUnavailableError
from app.models.document import (
    BlockType,
    BoundingBox,
    ChunkType,
    DocumentBlock,
    DocumentChunk,
    DocumentPage,
    DocumentRecord,
    DocumentStatus,
)


class PdfDocumentParser:
    def parse(self, document: DocumentRecord) -> DocumentRecord:
        if fitz is None:
            raise DependencyUnavailableError("PDF parsing dependency is unavailable")

        source_path = Path(document.storage_path)
        if not source_path.exists():
            raise BadRequestError(f"PDF file {source_path} does not exist")

        try:
            pdf = fitz.open(source_path)
        except Exception as exc:  # pragma: no cover - fitz raises several exception types
            raise BadRequestError(f"Unable to parse PDF {document.filename}") from exc

        pages: list[DocumentPage] = []
        chunks: list[DocumentChunk] = []
        try:
            for page_index in range(pdf.page_count):
                page = pdf.load_page(page_index)
                page_number = page_index + 1
                block_payloads = self._extract_blocks(document.document_id, page_number, page)
                text_blocks = [
                    block for block in block_payloads if block.block_type == BlockType.TEXT
                ]
                page_text = "\n".join(
                    block.text for block in text_blocks if block.text and block.text.strip()
                ).strip()
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document.document_id}-page-{page_number}",
                        document_id=document.document_id,
                        chunk_type=ChunkType.PAGE,
                        text=page_text,
                        page_numbers=[page_number],
                        source_block_ids=[block.block_id for block in block_payloads],
                        metadata={
                            "extraction_backend": "pymupdf",
                            "is_scanned_page": not bool(text_blocks),
                        },
                    )
                )
                pages.append(
                    DocumentPage(
                        page_number=page_number,
                        width=float(page.rect.width),
                        height=float(page.rect.height),
                        blocks=block_payloads,
                        metadata={
                            "extraction_backend": "pymupdf",
                            "is_scanned_page": not bool(text_blocks),
                            "block_count": len(block_payloads),
                        },
                    )
                )
        finally:
            pdf.close()

        now = datetime.now(timezone.utc)
        return document.model_copy(
            update={
                "status": DocumentStatus.READY,
                "page_count": len(pages),
                "pages": pages,
                "chunks": chunks,
                "updated_at": now,
            }
        )

    def _extract_blocks(
        self,
        document_id: str,
        page_number: int,
        page: Any,
    ) -> list[DocumentBlock]:
        payload = page.get_text("dict")
        blocks: list[DocumentBlock] = []
        for index, block in enumerate(payload.get("blocks", [])):
            block_type = self._map_block_type(block.get("type"))
            text = self._block_text(block)
            bbox = self._bbox(block.get("bbox"))
            block_id = f"{document_id}-p{page_number}-b{index}"
            if block_type == BlockType.TEXT and not text:
                continue
            blocks.append(
                DocumentBlock(
                    block_id=block_id,
                    page_number=page_number,
                    block_type=block_type,
                    text=text or None,
                    bbox=bbox,
                    reading_order=index,
                    metadata={
                        "raw_type": block.get("type"),
                        "line_count": len(block.get("lines", [])),
                    },
                )
            )
        return blocks

    @staticmethod
    def _map_block_type(raw_type: int | None) -> BlockType:
        if raw_type == 0:
            return BlockType.TEXT
        if raw_type == 1:
            return BlockType.FIGURE
        return BlockType.OTHER

    @staticmethod
    def _block_text(block: dict[str, Any]) -> str:
        lines: list[str] = []
        for line in block.get("lines", []):
            spans = [span.get("text", "") for span in line.get("spans", [])]
            line_text = "".join(spans).strip()
            if line_text:
                lines.append(line_text)
        return "\n".join(lines).strip()

    @staticmethod
    def _bbox(value: Any) -> BoundingBox | None:
        if not value or len(value) != 4:
            return None
        return BoundingBox(
            x0=float(value[0]),
            y0=float(value[1]),
            x1=float(value[2]),
            y1=float(value[3]),
        )