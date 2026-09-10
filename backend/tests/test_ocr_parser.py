"""Unit coverage for OCR fallback on scanned PDF pages."""

from datetime import datetime, timezone
from pathlib import Path

import fitz

from app.ingestion.ocr import OcrEngine
from app.ingestion.pdf_parser import PdfDocumentParser
from app.models.document import (
    BoundingBox,
    DocumentRecord,
    DocumentRegion,
    DocumentStatus,
    RegionType,
)


class FakeOcrEngine(OcrEngine):
    def extract(self, image_path: Path, page_number: int, document_id: str) -> list[DocumentRegion]:
        return [
            DocumentRegion(
                region_id=f"{document_id}-p{page_number}-ocr-0",
                page_number=page_number,
                region_type=RegionType.OCR_LINE,
                text=f"ocr text for page {page_number}",
                bbox=BoundingBox(x0=10, y0=12, x1=120, y1=34),
                confidence=0.91,
                source="ocr",
                metadata={"engine": "fake"},
            )
        ]


def _create_scanned_like_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=400, height=600)
    document.save(path)
    document.close()


def test_pdf_parser_uses_ocr_for_scanned_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _create_scanned_like_pdf(pdf_path)

    parser = PdfDocumentParser(ocr_engine=FakeOcrEngine())
    parsed = parser.parse(
        DocumentRecord(
            document_id="doc-ocr",
            filename="scanned.pdf",
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
    assert parsed.page_count == 1
    assert parsed.pages[0].metadata["is_scanned_page"] is True
    assert parsed.pages[0].regions[0].source == "ocr"
    assert parsed.pages[0].blocks[0].text == "ocr text for page 1"
    assert parsed.pages[0].blocks[0].bbox is not None
    assert parsed.chunks[0].text == "ocr text for page 1"