"""Hybrid retrieval endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.api.schemas import (
    RetrievalHitResponse,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
)
from app.core.config import Settings
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


def _get_retrieval_service(settings: Settings = Depends(get_app_settings)) -> RetrievalService:
    return RetrievalService(settings)


@router.post("/search", response_model=RetrievalQueryResponse)
def search(
    request: RetrievalQueryRequest,
    service: RetrievalService = Depends(_get_retrieval_service),
) -> RetrievalQueryResponse:
    results = service.search(
        query=request.query,
        limit=request.limit,
        document_id=request.document_id,
    )
    return RetrievalQueryResponse(
        query=request.query,
        result_count=len(results),
        results=[RetrievalHitResponse.model_validate(hit.model_dump()) for hit in results],
    )