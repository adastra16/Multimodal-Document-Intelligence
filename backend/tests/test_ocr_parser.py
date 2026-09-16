"""Unit coverage for OCR fallback on scanned PDF pages."""

from datetime import datetime, timezone
from pathlib import Path

import fitz
import pytest

from app.ingestion.ocr import OcrEngine, TesseractOcrEngine, tesseract_is_available
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


def _document_record(path: Path, document_id: str) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        filename=path.name,
        content_type="application/pdf",
        size_bytes=path.stat().st_size,
        storage_path=str(path),
        status=DocumentStatus.PROCESSING,
        page_count=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _create_scanned_like_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=400, height=600)
    document.save(path)
    document.close()


def _create_image_only_pdf(path: Path, text: str) -> None:
    source = fitz.open()
    page = source.new_page(width=400, height=200)
    page.insert_text((40, 80), text, fontsize=24)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    scanned = fitz.open()
    scanned_page = scanned.new_page(width=page.rect.width, height=page.rect.height)
    scanned_page.insert_image(scanned_page.rect, pixmap=pixmap)
    scanned.save(path)
    scanned.close()
    source.close()


def test_pdf_parser_uses_ocr_for_scanned_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _create_scanned_like_pdf(pdf_path)

    parser = PdfDocumentParser(ocr_engine=FakeOcrEngine())
    parsed = parser.parse(_document_record(pdf_path, "doc-ocr"))

    assert parsed.status == DocumentStatus.READY
    assert parsed.page_count == 1
    assert parsed.pages[0].metadata["is_scanned_page"] is True
    assert parsed.pages[0].regions[0].source == "ocr"
    assert parsed.pages[0].blocks[0].text == "ocr text for page 1"
    assert parsed.pages[0].blocks[0].bbox is not None
    assert parsed.chunks[0].text == "ocr text for page 1"


def test_tesseract_parses_word_tsv_into_line_regions() -> None:
    engine = TesseractOcrEngine()
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t40\t12\t90\tHello\n"
        "5\t1\t1\t1\t1\t2\t55\t20\t50\t12\t80\tWorld\n"
    )
    lines = engine._parse_tsv(tsv)
    assert len(lines) == 1
    assert lines[0].text == "Hello World"
    assert lines[0].bbox.x0 == 10
    assert lines[0].bbox.y0 == 20
    assert lines[0].bbox.x1 == 105
    assert lines[0].bbox.y1 == 32
    assert lines[0].confidence == pytest.approx(0.85)


@pytest.mark.skipif(not tesseract_is_available(), reason="Tesseract is not installed")
def test_tesseract_ocr_reads_image_only_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    _create_image_only_pdf(pdf_path, "WIKITQ TOTAL")
    parsed = PdfDocumentParser(ocr_engine=TesseractOcrEngine()).parse(
        _document_record(pdf_path, "doc-tesseract")
    )
    assert parsed.pages[0].metadata["is_scanned_page"] is True
    ocr_text = " ".join(
        region.text or "" for region in parsed.pages[0].regions if region.source == "ocr"
    ).upper()
    assert "WIKITQ" in ocr_text or "TOTAL" in ocr_text
    bbox = parsed.pages[0].regions[0].bbox
    assert bbox is not None
    assert bbox.x1 <= parsed.pages[0].width + 1
    assert bbox.y1 <= parsed.pages[0].height + 1
