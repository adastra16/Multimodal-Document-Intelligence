"""Citation-first answer generation with a safe extractive default."""

from __future__ import annotations

from app.models.generation import AnswerClaim, AnswerStatus, Citation, GroundedAnswer
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit


class GroundedAnswerGenerator:
    """Build answers only from retrieval evidence.

    The default output is extractive so it remains useful when no local LLM is
    running.  A later provider can replace this class but must emit the same
    citation-bearing claims before its output is returned to callers.
    """

    def __init__(self, minimum_score: float) -> None:
        self._minimum_score = minimum_score

    def generate(
        self,
        question: str,
        evidence_groups: list[RetrievalEvidenceGroup],
    ) -> GroundedAnswer:
        usable_groups = [
            group
            for group in evidence_groups
            if group.hits and group.hits[0].final_score >= self._minimum_score
        ]
        if not usable_groups:
            return GroundedAnswer(
                question=question,
                status=AnswerStatus.INSUFFICIENT_EVIDENCE,
                answer=(
                    "I cannot answer this from the uploaded documents because I could not "
                    "find enough supporting evidence."
                ),
                generation_mode="extractive",
            )

        claims = [self._claim_from_group(group) for group in usable_groups]
        return GroundedAnswer(
            question=question,
            status=AnswerStatus.ANSWERED,
            answer="\n\n".join(claim.text for claim in claims),
            claims=claims,
            evidence_group_ids=[group.group_id for group in usable_groups],
            generation_mode="extractive",
        )

    @staticmethod
    def _claim_from_group(group: RetrievalEvidenceGroup) -> AnswerClaim:
        # The anchor is query-relevant; expanded evidence remains available in
        # the group for the caller to inspect or use in a later synthesis stage.
        anchor = group.hits[0]
        return AnswerClaim(text=anchor.text, citations=[GroundedAnswerGenerator._citation(anchor)])

    @staticmethod
    def _citation(hit: RetrievalHit) -> Citation:
        return Citation(
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            page_numbers=hit.page_numbers,
            source_block_ids=hit.source_block_ids,
        )
