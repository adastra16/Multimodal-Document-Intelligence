"""Unit coverage for citation-first answer construction."""

from app.generation.grounded import GroundedAnswerGenerator
from app.models.document import ChunkType
from app.models.generation import AnswerStatus
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit


def _group(score: float = 0.8) -> RetrievalEvidenceGroup:
    hit = RetrievalHit(
        chunk_id="doc-1-page-1",
        document_id="doc-1",
        chunk_type=ChunkType.PAGE,
        text="Revenue increased by ten percent.",
        page_numbers=[1],
        source_block_ids=["doc-1-p1-b1"],
        lexical_score=score,
        semantic_score=score,
        hybrid_score=score,
        final_score=score,
    )
    return RetrievalEvidenceGroup(
        group_id="evidence-doc-1-page-1",
        document_id="doc-1",
        anchor_chunk_id=hit.chunk_id,
        page_numbers=[1],
        hits=[hit],
    )


def test_extractive_answer_keeps_claim_and_region_provenance() -> None:
    answer = GroundedAnswerGenerator(minimum_score=0.2).generate("What changed?", [_group()])

    assert answer.status == AnswerStatus.ANSWERED
    assert answer.generation_mode == "extractive"
    assert answer.claims[0].text == "Revenue increased by ten percent."
    assert answer.claims[0].citations[0].page_numbers == [1]
    assert answer.claims[0].citations[0].source_block_ids == ["doc-1-p1-b1"]


def test_extractive_answer_stays_concise_and_question_relevant() -> None:
    long_text = (
        "Figure 2: Architecture diagram of the pipeline. "
        "Revenue increased by ten percent. "
        "The board also discussed hiring. "
        "Facilities spending rose next. "
        "Marketing spend was unchanged. "
        "Legal costs declined slightly. "
        "A sixth unrelated paragraph should not appear. "
        "Revenue increased by ten percent."
    )
    group = _group()
    group.hits[0].text = long_text
    answer = GroundedAnswerGenerator(minimum_score=0.2).generate(
        "What percentage did revenue increase?",
        [group],
    )

    sentences = [part for part in answer.answer.replace("?", ".").split(".") if part.strip()]
    assert 2 <= len(sentences) <= 5
    assert "figure 2" not in answer.answer.lower()
    assert answer.answer.lower().count("revenue increased by ten percent") == 1
    assert "Revenue increased by ten percent." in answer.answer
    assert answer.claims[0].citations[0].page_numbers == [1]


def test_figure_chunks_are_not_used_as_answers() -> None:
    figure = _group()
    figure.hits[0].chunk_type = ChunkType.FIGURE
    figure.hits[0].text = "Figure 1. Sample caption from the scanned plate."
    answer = GroundedAnswerGenerator(minimum_score=0.2).generate("What is shown?", [figure])
    assert answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE


def test_generator_refuses_when_evidence_is_missing_or_weak() -> None:
    answer = GroundedAnswerGenerator(minimum_score=0.9).generate("What changed?", [_group()])

    assert answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert answer.claims == []
    assert "cannot answer" in answer.answer.lower()
