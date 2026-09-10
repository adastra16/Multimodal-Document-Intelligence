"""Small, deterministic second-stage reranking for laptop-friendly retrieval."""

from __future__ import annotations

import re

from app.models.retrieval import RetrievalHit


class DeterministicReranker:
    """Favor full query coverage after broad hybrid candidate retrieval.

    This deliberately has no model download or remote dependency.  A future local
    cross-encoder can implement the same ``rerank`` interface without changing the
    retrieval service.
    """

    def rerank(self, query: str, candidates: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        terms = set(re.findall(r"[A-Za-z0-9]+", query.lower()))
        normalized_query = " ".join(query.lower().split())
        ranked: list[RetrievalHit] = []
        for candidate in candidates:
            text_terms = set(re.findall(r"[A-Za-z0-9]+", candidate.text.lower()))
            coverage = len(terms & text_terms) / len(terms) if terms else 0.0
            phrase_bonus = (
                1.0
                if normalized_query and normalized_query in candidate.text.lower()
                else 0.0
            )
            score = (0.55 * candidate.hybrid_score) + (0.35 * coverage) + (0.10 * phrase_bonus)
            ranked.append(
                candidate.model_copy(
                    update={
                        "rerank_score": score,
                        "final_score": score,
                        "retrieval_stage": "reranked",
                    }
                )
            )
        ranked.sort(key=lambda hit: (hit.final_score, hit.hybrid_score), reverse=True)
        return ranked[:limit]
