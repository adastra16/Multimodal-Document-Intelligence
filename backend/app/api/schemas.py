"""Typed HTTP request/response contracts for the API layer."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.document import DocumentChunk, DocumentPage, DocumentStatus


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
