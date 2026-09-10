"""Document upload and lookup endpoints."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_app_settings
from app.api.schemas import (
    DocumentListResponse,
    DocumentSummaryResponse,
    DocumentUploadResponse,
)
from app.core.config import Settings
from app.models.document import DocumentRecord
from app.services.documents import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_summary(document: DocumentRecord) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        document_id=document.document_id,
        filename=document.filename,
        status=document.status,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        page_count=document.page_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _get_document_service(settings: Settings = Depends(get_app_settings)) -> DocumentService:
    return DocumentService(settings)


@router.post("", response_model=DocumentUploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    service: DocumentService = Depends(_get_document_service),
) -> DocumentUploadResponse:
    documents = await service.register_documents(files)
    return DocumentUploadResponse(documents=[_to_summary(document) for document in documents])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    service: DocumentService = Depends(_get_document_service),
) -> DocumentListResponse:
    documents = service.list_documents()
    return DocumentListResponse(documents=[_to_summary(document) for document in documents])


@router.get("/{document_id}", response_model=DocumentSummaryResponse)
def get_document(
    document_id: str,
    service: DocumentService = Depends(_get_document_service),
) -> DocumentSummaryResponse:
    return _to_summary(service.get_document(document_id))