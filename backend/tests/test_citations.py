"""Unit coverage for citation region hydration from canonical artifacts."""

from datetime import datetime, timezone

from app.core.config import Settings
from app.models.document import (
    BlockType,
    BoundingBox,
    DocumentBlock,
    DocumentPage,
    DocumentRecord,
    DocumentStatus,
)
from app.models.generation import AnswerClaim, AnswerStatus, Citation, GroundedAnswer
from app.persistence.documents import DocumentRepository
from app.services.citations import CitationService


def test_citation_service_resolves_filename_and_block_region(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'data' / 'app.db').as_posix()}",
    )
    now = datetime.now(timezone.utc)
    document = DocumentRecord(
        document_id="doc-1",
        filename="report.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_path=str(tmp_path / "report.pdf"),
        status=DocumentStatus.READY,
        created_at=now,
        updated_at=now,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="doc-1-p1-b1",
                        page_number=1,
                        block_type=BlockType.TEXT,
                        text="Revenue increased.",
                        bbox=BoundingBox(x0=10, y0=20, x1=100, y1=40),
                    )
                ],
            )
        ],
    )
    repository = DocumentRepository(settings)
    repository.insert(document)
    repository.save_artifact(document)
    answer = GroundedAnswer(
        question="What changed?",
        status=AnswerStatus.ANSWERED,
        answer="Revenue increased.",
        generation_mode="extractive",
        claims=[
            AnswerClaim(
                text="Revenue increased.",
                citations=[
                    Citation(
                        document_id="doc-1",
                        chunk_id="doc-1-page-1",
                        page_numbers=[1],
                        source_block_ids=["doc-1-p1-b1"],
                    )
                ],
            )
        ],
    )

    hydrated = CitationService(settings, repository).hydrate(answer)

    citation = hydrated.claims[0].citations[0]
    assert citation.filename == "report.pdf"
    assert citation.regions[0].block_id == "doc-1-p1-b1"
    assert citation.regions[0].bbox == BoundingBox(x0=10, y0=20, x1=100, y1=40)
