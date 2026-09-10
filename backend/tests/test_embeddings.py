"""Unit coverage for deterministic chunk embeddings and vector search."""

from app.core.config import Settings
from app.models.document import ChunkType, DocumentChunk
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel


def test_hashed_embeddings_are_deterministic_and_content_sensitive() -> None:
    model = HashedEmbeddingModel(dimensions=64)
    left = model.embed("alpha beta beta")
    right = model.embed("alpha beta beta")
    different = model.embed("zeta omega")

    assert left == right
    assert model.cosine_similarity(left, right) > model.cosine_similarity(left, different)


def test_vector_index_search_ranks_similar_text_higher(tmp_path) -> None:
    settings_path = tmp_path / "index.db"
    repository = VectorIndexRepository(
        Settings(app_env="test", database_url=f"sqlite:///{settings_path.as_posix()}")
    )
    model = HashedEmbeddingModel(dimensions=64)

    chunks = [
        DocumentChunk(
            chunk_id="chunk-a",
            document_id="doc-1",
            chunk_type=ChunkType.PAGE,
            text="alpha beta gamma",
            page_numbers=[1],
            source_block_ids=["a"],
        ),
        DocumentChunk(
            chunk_id="chunk-b",
            document_id="doc-1",
            chunk_type=ChunkType.PAGE,
            text="zeta theta lambda",
            page_numbers=[2],
            source_block_ids=["b"],
        ),
    ]
    repository.upsert_chunks(chunks, [model.embed(chunk.text) for chunk in chunks])

    results = repository.search(model.embed("alpha gamma"), limit=2)

    assert results[0]["chunk_id"] == "chunk-a"
    assert results[0]["score"] >= results[1]["score"]