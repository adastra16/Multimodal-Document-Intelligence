"""Domain models for answers that remain traceable to retrieved evidence."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    page_numbers: list[int] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)


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
