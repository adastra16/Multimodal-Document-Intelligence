"""Evaluation framework and benchmark harness for multimodal document intelligence."""

from app.evaluation.harness import EvaluationHarness
from app.evaluation.judge import (
    DeterministicFaithfulnessJudge,
    FaithfulnessJudge,
    LlmFaithfulnessJudge,
)
from app.evaluation.schemas import (
    AnswerEvaluation,
    EvaluationReport,
    EvaluationRun,
    GoldDataset,
    GoldSample,
    QuestionType,
    RetrievalEvaluation,
)

__all__ = [
    "AnswerEvaluation",
    "DeterministicFaithfulnessJudge",
    "EvaluationHarness",
    "EvaluationReport",
    "EvaluationRun",
    "FaithfulnessJudge",
    "GoldDataset",
    "GoldSample",
    "LlmFaithfulnessJudge",
    "QuestionType",
    "RetrievalEvaluation",
]
