# Evaluation results

This document records measured benchmark runs. The harness is run with:

```bash
python evaluation/run_eval.py
```

## Baseline versus Entity Bonus

| Run | Hit@1 | Hit@3 | Hit@5 | MRR | Mean page recall | Cross-page recall | Status accuracy | Faithfulness | Hallucination rate | Citation missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline (`eval_run_20260915_133932.json`) | 0.32 | 0.56 | 0.72 | 0.4453 | 0.80 | 1.00 | 0.92 | 1.00 | 0.08 | 9 |
| Entity Bonus (`eval_run_20260915_142308.json`) | 0.32 | 0.56 | 0.72 | 0.4473 | 0.80 | 1.00 | 0.92 | 1.00 | 0.08 | 9 |

The Entity Bonus experiment produced a negligible MRR increase of 0.0020. It did not improve Hit@1, Hit@3, Hit@5, page recall, answer status accuracy, faithfulness, hallucination rate, citation coverage, or cross-page recall. It is retained as an evaluated experiment; no multiplier was increased to force an apparent improvement.

## Gold-set page-alignment correction

The canonical parsed PDFs were checked before the final run. The evidence pages were corrected without changing questions, answers, keywords, or metrics:

- `eval-007`: page 2 → page 5.
- `eval-009`: page 10 → page 7.
- `eval-020`: pages 5 and 6, because both pages contain valid table evidence for the requested overall WIKITQ accuracy.

## Final corrected-gold run

The final run, `eval_run_20260916_120011.json`, used the corrected page references and the retained Entity Bonus reranker. It measured:

| Hit@1 | Hit@3 | Hit@5 | MRR | Mean page recall | Cross-page recall | Status accuracy | Faithfulness | Hallucination rate | Citation missing |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.36 | 0.68 | 0.84 | 0.5207 | 0.90 | 1.00 | 0.92 | 1.00 | 0.08 | 6 |

The improvement relative to the earlier runs comes from correcting verified ground-truth page alignment, not from a retrieval-algorithm change. Cross-page recall remains 1.00.
