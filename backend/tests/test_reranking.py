from app.models.document import ChunkType
from app.models.retrieval import RetrievalHit
from app.retrieval.reranking import DeterministicReranker


def _hit(chunk_id: str, text: str, hybrid_score: float) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_type=ChunkType.PAGE,
        text=text,
        page_numbers=[1],
        source_block_ids=[],
        lexical_score=hybrid_score,
        semantic_score=hybrid_score,
        hybrid_score=hybrid_score,
    )


def test_reranker_favors_complete_query_coverage() -> None:
    results = DeterministicReranker().rerank(
        "capital expenditure outlook",
        [
            _hit("partial", "capital expenditure mentioned", 0.8),
            _hit("complete", "capital expenditure outlook is stable", 0.72),
        ],
        limit=2,
    )

    assert results[0].chunk_id == "complete"
    assert results[0].retrieval_stage == "reranked"
    assert results[0].final_score == results[0].rerank_score


def test_reranker_dampens_candidates_without_salient_term_matches() -> None:
    results = DeterministicReranker().rerank(
        "Which European country had retail store revenue?",
        [
            _hit("unrelated", "Annual results improved in the fiscal year.", 0.9),
            _hit("relevant", "European retail store revenue was reported.", 0.5),
        ],
        limit=2,
    )

    assert results[0].chunk_id == "relevant"
    assert results[1].final_score < 0.15
    assert results[1].metadata["salient_matched_terms"] == []
