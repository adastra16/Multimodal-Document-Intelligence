"""Unit coverage for PDF parsing into canonical document structures."""

from datetime import datetime, timezone
from pathlib import Path

import fitz

from app.ingestion.ocr import OcrEngine
from app.ingestion.pdf_parser import PdfDocumentParser
from app.models.document import DocumentRecord, DocumentRegion, DocumentStatus


class _ExplodingOcrEngine(OcrEngine):
    def extract(self, image_path: Path, page_number: int, document_id: str) -> list[DocumentRegion]:
        raise AssertionError("native-text pages must not invoke OCR")


def _create_pdf(path: Path) -> None:
    document = fitz.open()
    page_one = document.new_page(width=400, height=600)
    page_one.insert_text((50, 50), "Page one text", fontsize=11)
    page_two = document.new_page(width=400, height=600)
    page_two.insert_text((50, 50), "Page two text", fontsize=11)
    document.save(path)
    document.close()


def test_pdf_parser_extracts_pages_blocks_and_chunks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "parser.pdf"
    _create_pdf(pdf_path)

    parser = PdfDocumentParser(ocr_engine=_ExplodingOcrEngine())
    parsed = parser.parse(
        DocumentRecord(
            document_id="doc-1",
            filename="parser.pdf",
            content_type="application/pdf",
            size_bytes=pdf_path.stat().st_size,
            storage_path=str(pdf_path),
            status=DocumentStatus.PROCESSING,
            page_count=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    assert parsed.status == DocumentStatus.READY
    assert parsed.page_count == 2
    assert len(parsed.pages) == 2
    assert parsed.pages[0].page_number == 1
    assert parsed.pages[0].blocks[0].block_type.value == "text"
    assert parsed.pages[0].metadata["is_scanned_page"] is False
    assert parsed.pages[0].regions[0].source == "native"
    assert any(chunk.chunk_type.value == "page" for chunk in parsed.chunks)
    assert any(chunk.chunk_type.value == "cross_page" for chunk in parsed.chunks)
