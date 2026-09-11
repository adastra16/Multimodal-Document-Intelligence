"""Unit tests for answer faithfulness judge and failure diagnostics."""

from app.core.config import Settings
from app.evaluation.judge import DeterministicFaithfulnessJudge, LlmFaithfulnessJudge
from app.models.document import BlockType
from app.models.generation import (
    AnswerClaim,
    AnswerStatus,
    Citation,
    CitationRegion,
    GroundedAnswer,
)


def _make_answer(status: AnswerStatus, text: str, claim_texts: list[str]) -> GroundedAnswer:
    citations = [
        Citation(
            document_id="doc1",
            chunk_id="c1",
            page_numbers=[1],
            regions=[CitationRegion(block_id="b1", page_number=1, block_type=BlockType.TEXT)],
        )
    ]
    claims = [AnswerClaim(text=ct, citations=citations) for ct in claim_texts]
    return GroundedAnswer(
        question="What is the revenue?",
        status=status,
        answer=text,
        claims=claims,
        evidence_group_ids=["g1"],
        generation_mode="hybrid",
    )


def test_deterministic_judge_supported_claims() -> None:
    judge = DeterministicFaithfulnessJudge(min_token_overlap=0.4)
    answer = _make_answer(
        AnswerStatus.ANSWERED,
        "Total revenue reached 120 million dollars in fiscal year 2024.",
        ["Total revenue reached 120 million dollars in fiscal year 2024."],
    )
    context = ["Acme Corp reported total revenue of 120 million dollars for fiscal year 2024."]
    score, details = judge.evaluate(answer, context)

    assert score == 1.0
    assert len(details) == 1
    assert details[0]["supported"] is True


def test_deterministic_judge_unsupported_claim() -> None:
    judge = DeterministicFaithfulnessJudge(min_token_overlap=0.4)
    answer = _make_answer(
        AnswerStatus.ANSWERED,
        "The company purchased three supersonic aircraft for executive transit.",
        ["The company purchased three supersonic aircraft for executive transit."],
    )
    context = ["Acme Corp reported total revenue of 120 million dollars for fiscal year 2024."]
    score, details = judge.evaluate(answer, context)

    assert score == 0.0
    assert len(details) == 1
    assert details[0]["supported"] is False


def test_judge_handles_insufficient_evidence_status() -> None:
    judge = DeterministicFaithfulnessJudge()
    answer = _make_answer(
        AnswerStatus.INSUFFICIENT_EVIDENCE,
        "I cannot answer this question based on the provided documents.",
        [],
    )
    score, details = judge.evaluate(answer, ["Some irrelevant text"])
    assert score == 1.0
    assert details == []


def test_llm_judge_fallback_on_unavailable_service() -> None:
    settings = Settings(llm_base_url="http://127.0.0.1:99999/v1", llm_model="test-model")
    judge = LlmFaithfulnessJudge(settings)
    answer = _make_answer(
        AnswerStatus.ANSWERED,
        "Revenue was 120M.",
        ["Revenue was 120M."],
    )
    context = ["Total revenue was 120M."]
    # Should cleanly fallback to deterministic judge without raising
    score, details = judge.evaluate(answer, context)
    assert score == 1.0
    assert details[0]["supported"] is True
