"""Domain models for answers that remain traceable to retrieved evidence."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.document import BlockType, BoundingBox


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    filename: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    regions: list[CitationRegion] = Field(default_factory=list)


class CitationRegion(BaseModel):
    """The source block a PDF viewer should highlight for a citation."""

    block_id: str
    page_number: int
    block_type: BlockType
    bbox: BoundingBox | None = None


class AnswerClaim(BaseModel):
    text: str
    citations: list[Citation] = Field(min_length=1)


class GroundedAnswer(BaseModel):
    question: str
    status: AnswerStatus
    answer: str
    claims: list[AnswerClaim] = Field(default_factory=list)
    evidence_group_ids: list[str] = Field(default_factory=list)
    generation_mode: str
