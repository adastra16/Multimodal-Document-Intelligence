"""Deterministic second-stage reranking with stopword-filtered salient entity coverage."""

from __future__ import annotations

import re

from app.models.retrieval import RetrievalHit

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "isn't", "it", "its", "itself", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "s", "t", "re",
}


class DeterministicReranker:
    """Favor salient entity coverage and penalize stopword-only token matches."""

    def rerank(self, query: str, candidates: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        all_terms = set(re.findall(r"[A-Za-z0-9]+", query.lower()))
        salient_terms = {t for t in all_terms if t not in STOPWORDS and len(t) > 1}
        target_terms = salient_terms if salient_terms else all_terms

        raw_terms = set(re.findall(r"[A-Za-z0-9]+", query))
        specific_entities = {
            t.lower() for t in raw_terms 
            if len(t) > 1 and t.lower() not in STOPWORDS and (any(c.isdigit() for c in t) or any(c.isupper() for c in t))
        }

        ranked: list[RetrievalHit] = []

        for candidate in candidates:
            text_terms = set(re.findall(r"[A-Za-z0-9]+", candidate.text.lower()))
            matched_salient = target_terms & text_terms
            matched_specific = specific_entities & text_terms

            coverage = len(matched_salient) / len(target_terms) if target_terms else 0.0
            entity_bonus = len(matched_specific) / len(specific_entities) if specific_entities else 0.0

            # If the query had salient terms but this chunk matched NONE of them,
            # heavily dampen the score to prevent false-positive hallucination.
            if salient_terms and not matched_salient:
                score = round(0.15 * candidate.hybrid_score, 4)
            else:
                score = round(
                    (0.45 * candidate.hybrid_score)
                    + (0.45 * coverage)
                    + (0.10 * entity_bonus),
                    4,
                )

            ranked.append(
                candidate.model_copy(
                    update={
                        "rerank_score": score,
                        "final_score": score,
                        "retrieval_stage": "reranked",
                        "metadata": {
                            **candidate.metadata,
                            "salient_matched_terms": sorted(matched_salient),
                        },
                    }
                )
            )

        ranked.sort(key=lambda hit: (hit.final_score, hit.hybrid_score), reverse=True)
        return ranked[:limit]
