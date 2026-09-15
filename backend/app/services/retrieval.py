"""Retrieval orchestration for hybrid keyword and semantic search."""

from __future__ import annotations

from app.core.config import Settings
from app.ingestion.chunking import StructureAwareChunker
from app.models.document import ChunkType, DocumentStatus
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit
from app.persistence.documents import DocumentRepository
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.context_expansion import CrossPageContextExpander
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.indexing import DocumentIndexer
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
    def __init__(
        self,
        settings: Settings,
        repository: VectorIndexRepository | None = None,
        document_repository: DocumentRepository | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or VectorIndexRepository(settings)
        self._document_repository = document_repository or DocumentRepository(settings)
        self._embedding_model = HashedEmbeddingModel(self._settings.embedding_dimensions)
        self._indexer = DocumentIndexer(self._repository, self._embedding_model)
        self._chunker = StructureAwareChunker()
        self._backfilled_document_ids: set[str] = set()
        self._retriever = HybridRetriever(
            self._repository,
            self._embedding_model,
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
        self._ensure_block_chunks(document_id)
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

    def _ensure_block_chunks(self, document_id: str | None) -> None:
        document_ids = [document_id] if document_id is not None else [
            document.document_id
            for document in self._document_repository.list_documents()
            if document.status == DocumentStatus.READY
        ]
        for current_document_id in document_ids:
            if current_document_id in self._backfilled_document_ids:
                continue
            if self._repository.has_chunk_type(current_document_id, ChunkType.BLOCK):
                self._backfilled_document_ids.add(current_document_id)
                continue
            document = self._document_repository.get_document(current_document_id)
            if not document.pages:
                continue
            updated_document = document.model_copy(
                update={"chunks": self._chunker.build(document)}
            )
            self._document_repository.save_artifact(updated_document)
            self._indexer.index(updated_document)
            self._backfilled_document_ids.add(current_document_id)
