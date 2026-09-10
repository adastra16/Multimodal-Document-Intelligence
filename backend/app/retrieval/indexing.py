"""Index parsed document chunks into the local vector store."""

from __future__ import annotations

from app.models.document import DocumentRecord
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel


class DocumentIndexer:
    def __init__(
        self,
        repository: VectorIndexRepository,
        embedding_model: HashedEmbeddingModel | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_model = embedding_model or HashedEmbeddingModel()

    def index(self, document: DocumentRecord) -> int:
        embeddings = [self._embedding_model.embed(chunk.text) for chunk in document.chunks]
        self._repository.upsert_chunks(document.chunks, embeddings)
        return len(document.chunks)

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[dict[str, object]]:
        query_embedding = self._embedding_model.embed(query)
        return self._repository.search(query_embedding, limit=limit, document_id=document_id)