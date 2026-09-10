"""Retrieval domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.document import ChunkType


class RetrievalHit(BaseModel):
    chunk_id: str
    document_id: str
    chunk_type: ChunkType
    text: str
    page_numbers: list[int] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    matched_terms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    rerank_score: float = 0.0
    final_score: float = 0.0
    retrieval_stage: str = "candidate"
    expanded_from_chunk_id: str | None = None


class RetrievalEvidenceGroup(BaseModel):
    """A seed hit together with the explicitly related evidence it brought in."""

    group_id: str
    document_id: str
    anchor_chunk_id: str
    page_numbers: list[int] = Field(default_factory=list)
    hits: list[RetrievalHit] = Field(default_factory=list)
