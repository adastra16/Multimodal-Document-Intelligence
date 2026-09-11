"""Unit tests for evaluation harness, schemas, and metric computations."""

from pathlib import Path

from app.evaluation.harness import EvaluationHarness
from app.evaluation.schemas import (
    AnswerEvaluation,
    GoldSample,
    QuestionType,
    RetrievalEvaluation,
)


def test_gold_dataset_loading(tmp_path: Path) -> None:
    dataset_file = tmp_path / "test_dataset.json"
    dataset_file.write_text(
        """
        {
            "name": "test_suite",
            "description": "A test suite",
            "version": "1.0.0",
            "samples": [
                {
                    "sample_id": "s1",
                    "document_filename": "doc.pdf",
                    "question": "What is the revenue?",
                    "question_type": "single_page_factoid",
                    "ground_truth_answer": "10M",
                    "ground_truth_pages": [1],
                    "ground_truth_keywords": ["10M"],
                    "requires_cross_page": false,
                    "expected_status": "answered"
                }
            ]
        }
        """,
        encoding="utf-8",
    )

    harness = EvaluationHarness()
    dataset = harness.load_dataset(dataset_file)
    assert dataset.name == "test_suite"
    assert len(dataset.samples) == 1
    assert dataset.samples[0].question_type == QuestionType.SINGLE_PAGE_FACTOID
    assert dataset.samples[0].ground_truth_pages == [1]


def test_compute_report_aggregation() -> None:
    samples = [
        GoldSample(
            sample_id="s1",
            document_filename="doc.pdf",
            question="Q1",
            question_type=QuestionType.SINGLE_PAGE_FACTOID,
            ground_truth_pages=[1],
            requires_cross_page=False,
        ),
        GoldSample(
            sample_id="s2",
            document_filename="doc.pdf",
            question="Q2",
            question_type=QuestionType.CROSS_PAGE_SYNTHESIS,
            ground_truth_pages=[1, 2],
            requires_cross_page=True,
        ),
    ]

    retrieval_evals = [
        RetrievalEvaluation(
            sample_id="s1",
            question="Q1",
            question_type=QuestionType.SINGLE_PAGE_FACTOID,
            hit_at_1=True,
            hit_at_3=True,
            hit_at_5=True,
            reciprocal_rank=1.0,
            page_recall=1.0,
            retrieved_pages=[1],
            top_chunks=["c1"],
        ),
        RetrievalEvaluation(
            sample_id="s2",
            question="Q2",
            question_type=QuestionType.CROSS_PAGE_SYNTHESIS,
            hit_at_1=False,
            hit_at_3=True,
            hit_at_5=True,
            reciprocal_rank=0.5,
            page_recall=1.0,
            retrieved_pages=[1, 2],
            top_chunks=["c2", "c3"],
        ),
    ]

    answer_evals = [
        AnswerEvaluation(
            sample_id="s1",
            question="Q1",
            status="answered",
            expected_status="answered",
            status_match=True,
            answer_text="Ans 1",
            cited_pages=[1],
            citation_page_recall=1.0,
            contains_expected_keywords=True,
        ),
        AnswerEvaluation(
            sample_id="s2",
            question="Q2",
            status="answered",
            expected_status="answered",
            status_match=True,
            answer_text="Ans 2",
            cited_pages=[1, 2],
            citation_page_recall=1.0,
            contains_expected_keywords=True,
        ),
    ]

    report = EvaluationHarness.compute_report(
        "test_bench", retrieval_evals, answer_evals, samples
    )

    assert report.total_samples == 2
    assert report.cross_page_samples == 1
    assert report.hit_at_1 == 0.5
    assert report.hit_at_3 == 1.0
    assert report.hit_at_5 == 1.0
    assert report.mean_reciprocal_rank == 0.75
    assert report.mean_page_recall == 1.0
    assert report.cross_page_recall == 1.0
    assert report.status_accuracy == 1.0
    assert report.keyword_containment_rate == 1.0


def test_empty_report_computation() -> None:
    report = EvaluationHarness.compute_report("empty", [], [], [])
    assert report.total_samples == 0
    assert report.hit_at_1 == 0.0
    assert report.mean_reciprocal_rank == 0.0
