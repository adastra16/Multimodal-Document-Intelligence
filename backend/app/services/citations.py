"""Resolve retrieval provenance into document/page/region citation payloads."""

from __future__ import annotations

from app.core.config import Settings
from app.models.document import DocumentRecord
from app.models.generation import CitationRegion, GroundedAnswer
from app.persistence.documents import DocumentRepository


class CitationService:
    def __init__(
        self,
        settings: Settings,
        repository: DocumentRepository | None = None,
    ) -> None:
        self._repository = repository or DocumentRepository(settings)

    def hydrate(self, answer: GroundedAnswer) -> GroundedAnswer:
        """Attach immutable artifact details to every citation in an answer."""
        documents: dict[str, DocumentRecord] = {}
        hydrated_claims = []
        for claim in answer.claims:
            hydrated_citations = []
            for citation in claim.citations:
                document = documents.setdefault(
                    citation.document_id,
                    self._repository.get_document(citation.document_id),
                )
                blocks = {
                    block.block_id: block
                    for page in document.pages
                    for block in page.blocks
                }
                regions = [
                    CitationRegion(
                        block_id=block.block_id,
                        page_number=block.page_number,
                        block_type=block.block_type,
                        bbox=block.bbox,
                    )
                    for block_id in citation.source_block_ids
                    if (block := blocks.get(block_id)) is not None
                ]
                hydrated_citations.append(
                    citation.model_copy(
                        update={"filename": document.filename, "regions": regions}
                    )
                )
            hydrated_claims.append(claim.model_copy(update={"citations": hydrated_citations}))
        return answer.model_copy(update={"claims": hydrated_claims})
