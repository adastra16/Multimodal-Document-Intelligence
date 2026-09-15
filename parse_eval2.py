import json
data = json.load(open('evaluation/results/eval_run_20260915_142308.json', encoding='utf-8'))
eval_ids = ['eval-002', 'eval-006', 'eval-008', 'eval-009', 'eval-012', 'eval-014', 'eval-016', 'eval-018', 'eval-020']
for r in data.get('retrieval_evaluations', []):
    if r['sample_id'] in eval_ids:
        print(f"{r['sample_id']}: type={r['question_type']}, hit@1={r['hit_at_1']}, hit@3={r['hit_at_3']}, hit@5={r['hit_at_5']}, pages={r['retrieved_pages'][:5]}")
