"""Evaluation harness for benchmark execution and metric calculation."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings, get_settings
from app.evaluation.schemas import (
    AnswerEvaluation,
    EvaluationReport,
    EvaluationRun,
    GoldDataset,
    GoldSample,
    RetrievalEvaluation,
)
from app.services.answers import AnswerService
from app.services.documents import DocumentService
from app.services.retrieval import RetrievalService


class EvaluationHarness:
    def __init__(
        self,
        settings: Settings | None = None,
        document_service: DocumentService | None = None,
        retrieval_service: RetrievalService | None = None,
        answer_service: AnswerService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._document_service = document_service or DocumentService(self._settings)
        self._retrieval_service = retrieval_service or RetrievalService(self._settings)
        self._answer_service = answer_service or AnswerService(
            self._settings,
            retrieval_service=self._retrieval_service,
        )

    def load_dataset(self, path: Path | str) -> GoldDataset:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        return GoldDataset.model_validate(data)

    def evaluate_retrieval_sample(
        self,
        sample: GoldSample,
        document_id: str | None = None,
        top_k: int = 5,
    ) -> RetrievalEvaluation:
        result = self._retrieval_service.search(
            query=sample.question,
            limit=top_k,
            document_id=document_id,
        )
        hits = result.results[:top_k]
        top_chunks = [hit.chunk_id for hit in hits]

        retrieved_pages: list[int] = []
        for hit in hits:
            for p in hit.page_numbers:
                if p not in retrieved_pages:
                    retrieved_pages.append(p)

        ground_truth_pages = set(sample.ground_truth_pages)
        hit_at_1 = bool(hits and any(p in ground_truth_pages for p in hits[0].page_numbers))
        hit_at_3 = bool(any(p in ground_truth_pages for hit in hits[:3] for p in hit.page_numbers))
        hit_at_5 = bool(any(p in ground_truth_pages for hit in hits[:5] for p in hit.page_numbers))

        reciprocal_rank = 0.0
        for rank, hit in enumerate(hits, start=1):
            if any(p in ground_truth_pages for p in hit.page_numbers):
                reciprocal_rank = 1.0 / rank
                break

        if ground_truth_pages:
            retrieved_gt = ground_truth_pages.intersection(retrieved_pages)
            page_recall = len(retrieved_gt) / len(ground_truth_pages)
        else:
            page_recall = 1.0

        return RetrievalEvaluation(
            sample_id=sample.sample_id,
            question=sample.question,
            question_type=sample.question_type,
            hit_at_1=hit_at_1,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            reciprocal_rank=reciprocal_rank,
            page_recall=page_recall,
            retrieved_pages=retrieved_pages,
            top_chunks=top_chunks,
        )

    def evaluate_answer_sample(
        self,
        sample: GoldSample,
        document_id: str | None = None,
    ) -> AnswerEvaluation:
        answer = self._answer_service.answer(
            question=sample.question,
            document_id=document_id,
        )

        status = answer.status.value
        status_match = status == sample.expected_status

        cited_pages: list[int] = []
        for claim in answer.claims:
            for citation in claim.citations:
                for p in citation.page_numbers:
                    if p not in cited_pages:
                        cited_pages.append(p)

        ground_truth_pages = set(sample.ground_truth_pages)
        if ground_truth_pages:
            cited_gt = ground_truth_pages.intersection(cited_pages)
            citation_page_recall = len(cited_gt) / len(ground_truth_pages)
        else:
            citation_page_recall = 1.0 if not cited_pages else 0.0

        contains_expected = True
        answer_lower = answer.answer.lower()
        if sample.ground_truth_keywords:
            contains_expected = any(
                kw.lower() in answer_lower for kw in sample.ground_truth_keywords
            )

        return AnswerEvaluation(
            sample_id=sample.sample_id,
            question=sample.question,
            status=status,
            expected_status=sample.expected_status,
            status_match=status_match,
            answer_text=answer.answer,
            cited_pages=cited_pages,
            citation_page_recall=citation_page_recall,
            contains_expected_keywords=contains_expected,
        )

    def run_benchmark(
        self,
        dataset: GoldDataset,
        document_id_map: dict[str, str] | None = None,
    ) -> EvaluationRun:
        document_id_map = document_id_map or {}
        retrieval_evals: list[RetrievalEvaluation] = []
        answer_evals: list[AnswerEvaluation] = []

        for sample in dataset.samples:
            doc_id = document_id_map.get(sample.document_filename)
            r_eval = self.evaluate_retrieval_sample(sample, document_id=doc_id)
            a_eval = self.evaluate_answer_sample(sample, document_id=doc_id)
            retrieval_evals.append(r_eval)
            answer_evals.append(a_eval)

        report = self.compute_report(dataset.name, retrieval_evals, answer_evals, dataset.samples)
        return EvaluationRun(
            report=report,
            retrieval_evaluations=retrieval_evals,
            answer_evaluations=answer_evals,
        )

    @staticmethod
    def compute_report(
        dataset_name: str,
        retrieval_evals: list[RetrievalEvaluation],
        answer_evals: list[AnswerEvaluation],
        samples: list[GoldSample],
    ) -> EvaluationReport:
        n = len(retrieval_evals)
        if n == 0:
            return EvaluationReport(
                dataset_name=dataset_name,
                total_samples=0,
                cross_page_samples=0,
                hit_at_1=0.0,
                hit_at_3=0.0,
                hit_at_5=0.0,
                mean_reciprocal_rank=0.0,
                mean_page_recall=0.0,
                cross_page_recall=0.0,
                status_accuracy=0.0,
                keyword_containment_rate=0.0,
            )

        hit_1 = sum(1 for e in retrieval_evals if e.hit_at_1) / n
        hit_3 = sum(1 for e in retrieval_evals if e.hit_at_3) / n
        hit_5 = sum(1 for e in retrieval_evals if e.hit_at_5) / n
        mrr = sum(e.reciprocal_rank for e in retrieval_evals) / n
        mpr = sum(e.page_recall for e in retrieval_evals) / n

        cross_page_pairs = [
            (e, s) for e, s in zip(retrieval_evals, samples) if s.requires_cross_page
        ]
        if cross_page_pairs:
            cross_page_recall = (
                sum(e.page_recall for e, _ in cross_page_pairs) / len(cross_page_pairs)
            )
        else:
            cross_page_recall = 1.0

        status_acc = sum(1 for a in answer_evals if a.status_match) / len(answer_evals)
        kw_rate = sum(1 for a in answer_evals if a.contains_expected_keywords) / len(answer_evals)

        return EvaluationReport(
            dataset_name=dataset_name,
            total_samples=n,
            cross_page_samples=len(cross_page_pairs),
            hit_at_1=round(hit_1, 4),
            hit_at_3=round(hit_3, 4),
            hit_at_5=round(hit_5, 4),
            mean_reciprocal_rank=round(mrr, 4),
            mean_page_recall=round(mpr, 4),
            cross_page_recall=round(cross_page_recall, 4),
            status_accuracy=round(status_acc, 4),
            keyword_containment_rate=round(kw_rate, 4),
        )
