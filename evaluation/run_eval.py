"""Evaluation runner CLI: executes the benchmark suite and outputs performance metrics."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to sys.path so app modules are resolvable
repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import get_settings
from app.evaluation.harness import EvaluationHarness
from app.services.documents import DocumentService


def run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmark over gold dataset for Multimodal Document Intelligence."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root / "evaluation" / "gold_dataset.json",
        help="Path to gold dataset JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "evaluation" / "results",
        help="Directory to save evaluation results.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks to evaluate for Hit@K.",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Error: Dataset not found at {args.dataset}", file=sys.stderr)
        return 1

    settings = get_settings()
    doc_service = DocumentService(settings)
    harness = EvaluationHarness(settings, document_service=doc_service)

    print(f"Loading gold dataset: {args.dataset}")
    dataset = harness.load_dataset(args.dataset)
    print(f"Loaded {len(dataset.samples)} samples from '{dataset.name}' (v{dataset.version})")

    # Evaluation fixtures are stored as internal documents and never appear in GET /documents.
    eval_data_dir = repo_root / "evaluation" / "data"
    doc_id_map: dict[str, str] = {}

    evaluation_filenames = {sample.document_filename for sample in dataset.samples}
    doc_service.prepare_evaluation_documents(evaluation_filenames)
    for sample in dataset.samples:
        filename = sample.document_filename
        if filename in doc_id_map:
            continue
        pdf_path = eval_data_dir / filename
        if not pdf_path.exists():
            print(f"Error: Required document not found: {pdf_path}", file=sys.stderr)
            print("Please place the required PDFs into evaluation/data/ before running the evaluation.", file=sys.stderr)
            return 1

        print(f"Refreshing evaluation PDF: {filename}...")
        record = doc_service.refresh_evaluation_document(pdf_path, filename=filename)
        doc_id_map[filename] = record.document_id
        print(f"Evaluation PDF ready: {filename} -> ID {record.document_id}")

    print("\nExecuting evaluation run...")
    eval_run = harness.run_benchmark(dataset, document_id_map=doc_id_map)
    report = eval_run.report

    # Output detailed results table
    print("\n" + "=" * 115)
    print(f"SAMPLE-BY-SAMPLE EVALUATION BREAKDOWN: {dataset.name}")
    print("=" * 115)
    header = (
        f"{'ID':<10} | {'Type':<22} | {'Hit@1':<5} | {'Hit@3':<5} | "
        f"{'MRR':<5} | {'PageRec':<7} | {'Faithful':<8} | {'Status':<6} | {'Failure Type':<22}"
    )
    print(header)
    print("-" * 115)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    for r_eval, a_eval in zip(eval_run.retrieval_evaluations, eval_run.answer_evaluations):
        h1 = "YES" if r_eval.hit_at_1 else "NO"
        h3 = "YES" if r_eval.hit_at_3 else "NO"
        sm = "YES" if a_eval.status_match else "NO"
        fail_desc = a_eval.failure_type or "none"

        line = (
            f"{r_eval.sample_id:<10} | "
            f"{r_eval.question_type.value:<22} | "
            f"{h1:<5} | "
            f"{h3:<5} | "
            f"{r_eval.reciprocal_rank:<5.2f} | "
            f"{r_eval.page_recall:<7.2f} | "
            f"{a_eval.faithfulness_score:<8.2f} | "
            f"{sm:<6} | "
            f"{fail_desc:<22}"
        )
        print(line)

    print("=" * 115)
    print("\n" + "=" * 50)
    print("AGGREGATE BENCHMARK PERFORMANCE REPORT")
    print("=" * 50)
    print(f"Total Samples Evaluated       : {report.total_samples}")
    print(f"Cross-Page Synthesis Samples  : {report.cross_page_samples}")
    print(f"Retrieval Hit@1               : {report.hit_at_1 * 100:.1f}%")
    print(f"Retrieval Hit@3               : {report.hit_at_3 * 100:.1f}%")
    print(f"Retrieval Hit@5               : {report.hit_at_5 * 100:.1f}%")
    print(f"Mean Reciprocal Rank (MRR)    : {report.mean_reciprocal_rank:.4f}")
    print(f"Mean Page Recall              : {report.mean_page_recall * 100:.1f}%")
    print(f"Cross-Page Recall             : {report.cross_page_recall * 100:.1f}%")
    print(f"Answer Status Accuracy        : {report.status_accuracy * 100:.1f}%")
    print(f"Keyword Groundedness Rate     : {report.keyword_containment_rate * 100:.1f}%")
    print(f"Mean Faithfulness Score       : {report.mean_faithfulness * 100:.1f}%")
    print(f"Hallucination Rate            : {report.hallucination_rate * 100:.1f}%")
    if report.failure_breakdown:
        print("\nFailure Case Breakdown:")
        for f_type, count in report.failure_breakdown.items():
            print(f"  - {f_type:<28}: {count} instance(s)")
    else:
        print("\nFailure Case Breakdown: Zero failures detected.")
    print("=" * 50)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = args.output_dir / f"eval_run_{timestamp_str}.json"
    out_file.write_text(eval_run.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved full benchmark report to: {out_file}\n")

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
