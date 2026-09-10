from app.models.document import ChunkType
from app.models.retrieval import RetrievalHit
from app.retrieval.context_expansion import CrossPageContextExpander


def _hit(
    chunk_id: str, chunk_type: ChunkType, pages: list[int], parent: str | None = None
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_type=chunk_type,
        text=chunk_id,
        page_numbers=pages,
        source_block_ids=[],
        lexical_score=0.5,
        semantic_score=0.5,
        hybrid_score=0.5,
        rerank_score=0.8,
        final_score=0.8,
        metadata={"parent_chunk_id": parent},
    )


def test_expansion_includes_cross_page_bridge_and_adjacent_page() -> None:
    anchor = _hit("page-1", ChunkType.PAGE, [1])
    bridge = _hit("bridge-1-2", ChunkType.CROSS_PAGE, [1, 2], parent="page-1")
    page_two = _hit("page-2", ChunkType.PAGE, [2])

    groups = CrossPageContextExpander().expand([anchor], [anchor, bridge, page_two], per_seed=3)

    assert groups[0].page_numbers == [1, 2]
    assert [hit.metadata["evidence_role"] for hit in groups[0].hits] == [
        "anchor",
        "child",
        "adjacent_page",
    ]
    assert groups[0].hits[1].expanded_from_chunk_id == "page-1"
