"""Canonical document domain models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BlockType(str, Enum):
    TEXT = "text"
    TITLE = "title"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    LIST_ITEM = "list_item"
    HEADER = "header"
    FOOTER = "footer"
    OTHER = "other"


class RegionType(str, Enum):
    TEXT = "text"
    OCR_LINE = "ocr_line"
    OCR_WORD = "ocr_word"
    FIGURE = "figure"
    TABLE = "table"
    CAPTION = "caption"
    OTHER = "other"


class ChunkType(str, Enum):
    PAGE = "page"
    SECTION = "section"
    WINDOW = "window"
    TABLE = "table"
    FIGURE = "figure"
    CROSS_PAGE = "cross_page"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentOrigin(str, Enum):
    """Identifies whether a document belongs to the product UI or an internal benchmark."""

    USER_UPLOAD = "user_upload"
    EVALUATION = "evaluation"


class BoundingBox(BaseModel):
    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)


class DocumentBlock(BaseModel):
    block_id: str
    page_number: int = Field(ge=1)
    block_type: BlockType
    text: str | None = None
    bbox: BoundingBox | None = None
    reading_order: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRegion(BaseModel):
    region_id: str
    page_number: int = Field(ge=1)
    region_type: RegionType
    text: str | None = None
    bbox: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str = Field(default="native")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentPage(BaseModel):
    page_number: int = Field(ge=1)
    width: float | None = None
    height: float | None = None
    blocks: list[DocumentBlock] = Field(default_factory=list)
    regions: list[DocumentRegion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_type: ChunkType
    text: str
    page_numbers: list[int] = Field(default_factory=list)
    parent_chunk_id: str | None = None
    child_chunk_ids: list[str] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_type", mode="before")
    @classmethod
    def _coerce_legacy_chunk_type(cls, value: object) -> object:
        """Map the reverted block-retrieval experiment onto window chunks."""
        if value == "block":
            return ChunkType.WINDOW
        return value


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    origin: DocumentOrigin = DocumentOrigin.USER_UPLOAD
    status: DocumentStatus
    page_count: int | None = None
    created_at: datetime
    updated_at: datetime
    pages: list[DocumentPage] = Field(default_factory=list)
    chunks: list[DocumentChunk] = Field(default_factory=list)
