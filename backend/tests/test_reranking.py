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
