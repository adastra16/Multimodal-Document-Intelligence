"""Data models and typed contracts for evaluation benchmarks and metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    SINGLE_PAGE_FACTOID = "single_page_factoid"
    CROSS_PAGE_SYNTHESIS = "cross_page_synthesis"
    TABLE_LOOKUP = "table_lookup"
    UNANSWERABLE_NEGATIVE = "unanswerable_negative"


class GoldSample(BaseModel):
    sample_id: str
    document_filename: str
    question: str
    question_type: QuestionType
    ground_truth_answer: str | None = None
    ground_truth_pages: list[int] = Field(default_factory=list)
    ground_truth_keywords: list[str] = Field(default_factory=list)
    requires_cross_page: bool = False
    expected_status: str = "answered"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoldDataset(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    samples: list[GoldSample] = Field(min_length=1)


class RetrievalEvaluation(BaseModel):
    sample_id: str
    question: str
    question_type: QuestionType
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    page_recall: float = Field(ge=0.0, le=1.0)
    retrieved_pages: list[int] = Field(default_factory=list)
    top_chunks: list[str] = Field(default_factory=list)


class AnswerEvaluation(BaseModel):
    sample_id: str
    question: str
    status: str
    expected_status: str
    status_match: bool
    answer_text: str
    cited_pages: list[int] = Field(default_factory=list)
    citation_page_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    contains_expected_keywords: bool = False
    faithfulness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    hallucination_detected: bool = False
    failure_type: str | None = None
    claim_evaluations: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    dataset_name: str
    total_samples: int
    cross_page_samples: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mean_reciprocal_rank: float
    mean_page_recall: float
    cross_page_recall: float
    status_accuracy: float
    keyword_containment_rate: float
    mean_faithfulness: float = 1.0
    hallucination_rate: float = 0.0
    failure_breakdown: dict[str, int] = Field(default_factory=dict)


class EvaluationRun(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    report: EvaluationReport
    retrieval_evaluations: list[RetrievalEvaluation] = Field(default_factory=list)
    answer_evaluations: list[AnswerEvaluation] = Field(default_factory=list)
