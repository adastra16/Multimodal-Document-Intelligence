"""Grounded question-answering endpoint."""

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.api.schemas import AnswerQueryRequest, AnswerResponse
from app.core.config import Settings
from app.services.answers import AnswerService

router = APIRouter(prefix="/answers", tags=["answers"])


def _get_answer_service(settings: Settings = Depends(get_app_settings)) -> AnswerService:
    return AnswerService(settings)


@router.post("", response_model=AnswerResponse)
def answer_question(
    request: AnswerQueryRequest,
    service: AnswerService = Depends(_get_answer_service),
) -> AnswerResponse:
    answer = service.answer(
        question=request.question,
        document_id=request.document_id,
        retrieval_limit=request.retrieval_limit,
    )
    return AnswerResponse.model_validate(answer.model_dump())
