"""Citation-first answer generation with a safe extractive default."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.document import ChunkType
from app.models.generation import AnswerClaim, AnswerStatus, Citation, GroundedAnswer
from app.models.retrieval import RetrievalEvidenceGroup, RetrievalHit

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}
_CAPTION_RE = re.compile(
    r"^(fig(?:ure)?|table|image|caption)\s*[\d.:)]",
    re.IGNORECASE,
)
_SKIP_CHUNK_TYPES = {ChunkType.FIGURE}


@dataclass(frozen=True)
class _ScoredSentence:
    text: str
    score: int
    hit: RetrievalHit


class GroundedAnswerGenerator:
    """Build a short, citation-bearing answer from retrieval evidence.

    The default output is extractive so it remains useful when no local LLM is
    running. Sentences are filtered and ranked so callers never receive raw
    retrieved chunks, figure captions, or duplicated boilerplate.
    """

    _MAX_SENTENCES = 5
    _MIN_SENTENCES = 2
    _MAX_SENTENCE_CHARS = 220

    def __init__(self, minimum_score: float) -> None:
        self._minimum_score = minimum_score

    def generate(
        self,
        question: str,
        evidence_groups: list[RetrievalEvidenceGroup],
    ) -> GroundedAnswer:
        usable_groups = [
            group
            for group in evidence_groups
            if group.hits
            and group.hits[0].final_score >= self._minimum_score
            and group.hits[0].chunk_type not in _SKIP_CHUNK_TYPES
        ]
        if not usable_groups:
            return self._insufficient(question)

        claims = self._claims_from_groups(question, usable_groups)
        if not claims:
            return self._insufficient(question)

        return GroundedAnswer(
            question=question,
            status=AnswerStatus.ANSWERED,
            answer=" ".join(claim.text for claim in claims),
            claims=claims,
            evidence_group_ids=[group.group_id for group in usable_groups],
            generation_mode="extractive",
        )

    @staticmethod
    def _insufficient(question: str) -> GroundedAnswer:
        return GroundedAnswer(
            question=question,
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            answer=(
                "I cannot answer this from the uploaded documents because I could not "
                "find enough supporting evidence."
            ),
            generation_mode="extractive",
        )

    @staticmethod
    def _claims_from_groups(
        question: str,
        groups: list[RetrievalEvidenceGroup],
    ) -> list[AnswerClaim]:
        terms = GroundedAnswerGenerator._question_terms(question)
        candidates = GroundedAnswerGenerator._candidate_sentences(groups, terms)
        selected = GroundedAnswerGenerator._select_sentences(candidates)
        return [
            AnswerClaim(
                text=item.text,
                citations=[GroundedAnswerGenerator._citation(item.hit)],
            )
            for item in selected
        ]

    @staticmethod
    def _candidate_sentences(
        groups: list[RetrievalEvidenceGroup],
        terms: set[str],
    ) -> list[_ScoredSentence]:
        candidates: list[_ScoredSentence] = []
        seen: set[str] = set()
        for group in groups:
            hit = group.hits[0]
            for sentence in GroundedAnswerGenerator._split_sentences(hit.text):
                cleaned = GroundedAnswerGenerator._clean_sentence(sentence)
                if cleaned is None:
                    continue
                key = GroundedAnswerGenerator._normalize(cleaned)
                if not key or key in seen or GroundedAnswerGenerator._is_duplicate(key, seen):
                    continue
                seen.add(key)
                score = GroundedAnswerGenerator._overlap(key, terms)
                candidates.append(_ScoredSentence(text=cleaned, score=score, hit=hit))
        return candidates

    @staticmethod
    def _select_sentences(candidates: list[_ScoredSentence]) -> list[_ScoredSentence]:
        if not candidates:
            return []
        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        relevant = [item for item in ranked if item.score > 0]
        extras = [item for item in ranked if item.score <= 0]
        pool = relevant + extras
        take = min(GroundedAnswerGenerator._MAX_SENTENCES, len(pool))
        if take == 1 and len(pool) >= GroundedAnswerGenerator._MIN_SENTENCES:
            take = GroundedAnswerGenerator._MIN_SENTENCES
        chosen = pool[:take]
        # Preserve reading order from the source hits instead of rank order.
        order = {id(item): index for index, item in enumerate(candidates)}
        return sorted(chosen, key=lambda item: order[id(item)])

    @staticmethod
    def _clean_sentence(text: str) -> str | None:
        cleaned = " ".join(text.split()).strip()
        if not cleaned or _CAPTION_RE.match(cleaned):
            return None
        lowered = cleaned.lower()
        if lowered.startswith(("figure ", "fig.", "table ")) and len(cleaned.split()) <= 12:
            return None
        return GroundedAnswerGenerator._truncate(cleaned)

    @staticmethod
    def _question_terms(question: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", question.lower())
            if token not in _STOPWORDS and len(token) > 1
        }

    @staticmethod
    def _overlap(normalized_sentence: str, terms: set[str]) -> int:
        if not terms:
            return 0
        words = set(normalized_sentence.split())
        return sum(1 for term in terms if term in words or any(term in word for word in words))

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _is_duplicate(key: str, seen: set[str]) -> bool:
        return any(key in existing or existing in key for existing in seen if existing)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences: list[str] = []
        current: list[str] = []
        for token in text.split():
            current.append(token)
            if token[-1:] in ".!?":
                sentences.append(" ".join(current).strip())
                current = []
        if current:
            sentences.append(" ".join(current).strip())
        return [sentence for sentence in sentences if sentence]

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= GroundedAnswerGenerator._MAX_SENTENCE_CHARS:
            return text
        clipped = text[: GroundedAnswerGenerator._MAX_SENTENCE_CHARS].rsplit(" ", 1)[0]
        return f"{clipped}..."

    @staticmethod
    def _citation(hit: RetrievalHit) -> Citation:
        return Citation(
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            page_numbers=hit.page_numbers,
            source_block_ids=hit.source_block_ids,
        )
