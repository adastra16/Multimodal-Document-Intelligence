"""Hybrid keyword and semantic retrieval over indexed document chunks."""

from __future__ import annotations

import re
from collections import Counter
from typing import cast

from app.models.document import ChunkType
from app.models.retrieval import RetrievalHit
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel


class HybridRetriever:
    def __init__(
        self,
        repository: VectorIndexRepository,
        embedding_model: HashedEmbeddingModel | None = None,
        semantic_weight: float = 0.65,
        lexical_weight: float = 0.35,
    ) -> None:
        weight_total = semantic_weight + lexical_weight
        if weight_total <= 0:
            raise ValueError("At least one retrieval weight must be positive")

        self._repository = repository
        self._embedding_model = embedding_model or HashedEmbeddingModel()
        self._semantic_weight = semantic_weight / weight_total
        self._lexical_weight = lexical_weight / weight_total

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[RetrievalHit]:
        query_tokens = self._tokenize(query)
        query_embedding = self._embedding_model.embed(query)

        hits: list[RetrievalHit] = []
        for candidate in self._repository.list_chunks():
            if document_id is not None and candidate["document_id"] != document_id:
                continue

            candidate_text = str(candidate["text"])
            candidate_embedding = candidate.get("embedding")
            if not isinstance(candidate_embedding, list):
                continue

            semantic_score = self._embedding_model.cosine_similarity(
                query_embedding,
                candidate_embedding,
            )
            lexical_score, matched_terms = self._lexical_score(query_tokens, candidate_text)
            hybrid_score = (
                self._semantic_weight * semantic_score
                + self._lexical_weight * lexical_score
            )
            chunk_type = cast(ChunkType, candidate["chunk_type"])
            page_numbers = cast(list[int], candidate["page_numbers"])
            source_block_ids = cast(list[str], candidate["source_block_ids"])
            embedding_dim = cast(int, candidate["embedding_dim"])
            hits.append(
                RetrievalHit(
                    chunk_id=str(candidate["chunk_id"]),
                    document_id=str(candidate["document_id"]),
                    chunk_type=chunk_type,
                    text=candidate_text,
                    page_numbers=page_numbers,
                    source_block_ids=source_block_ids,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    hybrid_score=hybrid_score,
                    matched_terms=matched_terms,
                    metadata={
                        "chunk_type": chunk_type.value,
                        "embedding_dim": embedding_dim,
                        "parent_chunk_id": candidate.get("parent_chunk_id"),
                    },
                )
            )

        hits.sort(key=lambda item: item.hybrid_score, reverse=True)
        return hits[:limit]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]+", text.lower())

    @staticmethod
    def _lexical_score(query_tokens: list[str], candidate_text: str) -> tuple[float, list[str]]:
        if not query_tokens:
            return 0.0, []

        candidate_tokens = re.findall(r"[A-Za-z0-9]+", candidate_text.lower())
        if not candidate_tokens:
            return 0.0, []

        query_counts = Counter(query_tokens)
        candidate_counts = Counter(candidate_tokens)
        overlap_terms = sorted(set(query_tokens) & set(candidate_tokens))
        if not overlap_terms:
            return 0.0, []

        overlap_weight = sum(
            min(query_counts[token], candidate_counts[token]) for token in overlap_terms
        )
        recall = overlap_weight / max(len(query_tokens), 1)
        precision = overlap_weight / max(len(candidate_tokens), 1)
        return (0.7 * recall) + (0.3 * precision), overlap_terms
