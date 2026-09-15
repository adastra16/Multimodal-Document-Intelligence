"""Retrieval orchestration for hybrid keyword and semantic search."""

from __future__ import annotations

from app.core.config import Settings
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.context_expansion import CrossPageContextExpander
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranking import DeterministicReranker


class RetrievalResult:
    def __init__(
        self,
        results: list[RetrievalHit],
        evidence_groups: list[RetrievalEvidenceGroup],
    ) -> None:
        self.results = results
        self.evidence_groups = evidence_groups


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
        self._reranker = DeterministicReranker()
        self._expander = CrossPageContextExpander()

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: str | None = None,
    ) -> RetrievalResult:
        candidate_limit = max(limit, limit * self._settings.retrieval_candidate_multiplier)
        candidates = self._retriever.search(
            query=query, limit=candidate_limit, document_id=document_id
        )
        reranked = self._reranker.rerank(query, candidates, limit=limit)
        anchors = reranked[: self._settings.retrieval_rerank_seed_limit]
        evidence_groups = self._expander.expand(
            anchors,
            candidates,
            per_seed=self._settings.retrieval_expansion_per_seed,
        )
        return RetrievalResult(results=reranked, evidence_groups=evidence_groups)
