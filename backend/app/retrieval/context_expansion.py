"""Expand reranked seeds into parent/child and neighboring-page evidence groups."""

from __future__ import annotations

from app.models.document import ChunkType
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit


class CrossPageContextExpander:
    def expand(
        self,
        anchors: list[RetrievalHit],
        candidates: list[RetrievalHit],
        per_seed: int,
    ) -> list[RetrievalEvidenceGroup]:
        groups: list[RetrievalEvidenceGroup] = []
        for anchor in anchors:
            related = self._related(anchor, candidates)
            selected = related[:per_seed]
            group_id = f"evidence-{anchor.chunk_id}"
            anchor_hit = anchor.model_copy(
                update={
                    "retrieval_stage": "anchor",
                    "metadata": {
                        **anchor.metadata,
                        "evidence_group_id": group_id,
                        "evidence_role": "anchor",
                    },
                }
            )
            expanded_hits = [anchor_hit]
            for relationship, hit in selected:
                expanded_hits.append(
                    hit.model_copy(
                        update={
                            "final_score": anchor.final_score * 0.8 + hit.hybrid_score * 0.2,
                            "retrieval_stage": "expanded",
                            "expanded_from_chunk_id": anchor.chunk_id,
                            "metadata": {
                                **hit.metadata,
                                "evidence_group_id": group_id,
                                "evidence_role": relationship,
                            },
                        }
                    )
                )
            pages = sorted({page for hit in expanded_hits for page in hit.page_numbers})
            groups.append(
                RetrievalEvidenceGroup(
                    group_id=group_id,
                    document_id=anchor.document_id,
                    anchor_chunk_id=anchor.chunk_id,
                    page_numbers=pages,
                    hits=expanded_hits,
                )
            )
        return groups

    def _related(
        self, anchor: RetrievalHit, candidates: list[RetrievalHit]
    ) -> list[tuple[str, RetrievalHit]]:
        related: list[tuple[int, str, RetrievalHit]] = []
        anchor_pages = set(anchor.page_numbers)
        for candidate in candidates:
            if candidate.chunk_id == anchor.chunk_id or candidate.document_id != anchor.document_id:
                continue
            parent_id = candidate.metadata.get("parent_chunk_id")
            if parent_id == anchor.chunk_id:
                related.append((0, "child", candidate))
            elif anchor.metadata.get("parent_chunk_id") == candidate.chunk_id:
                related.append((0, "parent", candidate))
            elif (
                candidate.chunk_type == ChunkType.CROSS_PAGE
                and anchor_pages.intersection(candidate.page_numbers)
            ):
                related.append((1, "cross_page_bridge", candidate))
            elif candidate.chunk_type == ChunkType.PAGE and any(
                abs(candidate_page - anchor_page) == 1
                for candidate_page in candidate.page_numbers
                for anchor_page in anchor_pages
            ):
                related.append((2, "adjacent_page", candidate))
        related.sort(key=lambda item: (item[0], -item[2].hybrid_score, item[2].chunk_id))
        return [(relationship, hit) for _, relationship, hit in related]
