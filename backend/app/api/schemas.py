"""Typed HTTP request/response contracts for the API layer."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.document import ChunkType, DocumentChunk, DocumentPage, DocumentStatus


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    version: str
    env: str


class DocumentSummaryResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    content_type: str
    size_bytes: int
    page_count: int | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummaryResponse]


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentSummaryResponse]


class DocumentDetailResponse(DocumentSummaryResponse):
    pages: list[DocumentPage]
    chunks: list[DocumentChunk]


class RetrievalQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None


class RetrievalHitResponse(BaseModel):
    chunk_id: str
    document_id: str
    chunk_type: ChunkType
    text: str
    page_numbers: list[int]
    source_block_ids: list[str]
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    matched_terms: list[str]
    metadata: dict[str, object]
    rerank_score: float
    final_score: float
    retrieval_stage: str
    expanded_from_chunk_id: str | None


class RetrievalEvidenceGroupResponse(BaseModel):
    group_id: str
    document_id: str
    anchor_chunk_id: str
    page_numbers: list[int]
    hits: list[RetrievalHitResponse]


class RetrievalQueryResponse(BaseModel):
    query: str
    result_count: int
    results: list[RetrievalHitResponse]
    evidence_groups: list[RetrievalEvidenceGroupResponse]
