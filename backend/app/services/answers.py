"""Answer orchestration: retrieve evidence first, then generate a grounded answer."""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.generation.grounded import GroundedAnswerGenerator
from app.models.generation import GroundedAnswer
from app.services.citations import CitationService
from app.services.retrieval import RetrievalService

logger = get_logger(__name__)


class AnswerService:
    def __init__(
        self,
        settings: Settings,
        retrieval_service: RetrievalService | None = None,
        citation_service: CitationService | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service or RetrievalService(settings)
        self._generator = GroundedAnswerGenerator(settings.generation_min_evidence_score)
        self._citation_service = citation_service or CitationService(settings)

    def answer(
        self,
        question: str,
        document_id: str | None = None,
        retrieval_limit: int = 5,
    ) -> GroundedAnswer:
        retrieval_result = self._retrieval_service.search(
            query=question,
            limit=retrieval_limit,
            document_id=document_id,
        )
        answer = self._generator.generate(question, retrieval_result.evidence_groups)
        hydrated_answer = self._citation_service.hydrate(answer)
        logger.info(
            "grounded_answer_generated",
            document_id=document_id,
            status=hydrated_answer.status.value,
            claim_count=len(hydrated_answer.claims),
            evidence_group_count=len(hydrated_answer.evidence_group_ids),
        )
        return hydrated_answer
