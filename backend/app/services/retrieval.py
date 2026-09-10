"""Retrieval orchestration for hybrid keyword and semantic search."""

from __future__ import annotations

from app.core.config import Settings
from app.models.retrieval import RetrievalHit
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.hybrid import HybridRetriever


class RetrievalService:
    def __init__(self, settings: Settings, repository: VectorIndexRepository | None = None) -> None:
        self._settings = settings
        self._repository = repository or VectorIndexRepository(settings)
        self._retriever = HybridRetriever(
            self._repository,
            HashedEmbeddingModel(self._settings.embedding_dimensions),
            semantic_weight=self._settings.retrieval_semantic_weight,
            lexical_weight=self._settings.retrieval_lexical_weight,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[RetrievalHit]:
        return self._retriever.search(query=query, limit=limit, document_id=document_id)