"""Unit coverage for hybrid keyword and semantic retrieval."""

from app.core.config import Settings
from app.models.document import ChunkType, DocumentChunk
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.hybrid import HybridRetriever


def test_hybrid_retriever_prefers_keyword_matches(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'hybrid.db').as_posix()}",
    )
    repository = VectorIndexRepository(settings)
    model = HashedEmbeddingModel(dimensions=64)

    chunks = [
        DocumentChunk(
            chunk_id="chunk-alpha",
            document_id="doc-1",
            chunk_type=ChunkType.PAGE,
            text="alpha claim shared conclusion",
            page_numbers=[1],
            source_block_ids=["a"],
        ),
        DocumentChunk(
            chunk_id="chunk-beta",
            document_id="doc-1",
            chunk_type=ChunkType.PAGE,
            text="beta unrelated passage",
            page_numbers=[2],
            source_block_ids=["b"],
        ),
    ]
    repository.upsert_chunks(chunks, [model.embed(chunk.text) for chunk in chunks])

    retriever = HybridRetriever(repository, model)
    results = retriever.search("shared claim", limit=2)

    assert results[0].chunk_id == "chunk-alpha"
    assert results[0].lexical_score > results[1].lexical_score
    assert "shared" in results[0].matched_terms


def test_hybrid_retriever_document_scope_filters_results(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'hybrid.db').as_posix()}",
    )
    repository = VectorIndexRepository(settings)
    model = HashedEmbeddingModel(dimensions=64)

    chunks = [
        DocumentChunk(
            chunk_id="chunk-one",
            document_id="doc-1",
            chunk_type=ChunkType.PAGE,
            text="alpha shared evidence",
            page_numbers=[1],
            source_block_ids=["a"],
        ),
        DocumentChunk(
            chunk_id="chunk-two",
            document_id="doc-2",
            chunk_type=ChunkType.PAGE,
            text="alpha shared evidence",
            page_numbers=[1],
            source_block_ids=["b"],
        ),
    ]
    repository.upsert_chunks(chunks, [model.embed(chunk.text) for chunk in chunks])

    retriever = HybridRetriever(repository, model)
    results = retriever.search("shared evidence", document_id="doc-2", limit=5)

    assert len(results) == 1
    assert results[0].document_id == "doc-2"