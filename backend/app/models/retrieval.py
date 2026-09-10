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