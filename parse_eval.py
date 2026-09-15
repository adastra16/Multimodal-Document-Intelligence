import json
data = json.load(open('evaluation/results/eval_run_20260915_133932.json', encoding='utf-8'))
eval_ids = ['eval-002', 'eval-006', 'eval-008', 'eval-009', 'eval-012', 'eval-014', 'eval-016', 'eval-018', 'eval-020']
for r in data.get('retrieval_evaluations', []):
    if r['sample_id'] in eval_ids:
        print(f"{r['sample_id']}: hit@1={r['hit_at_1']}, hit@3={r['hit_at_3']}, hit@5={r['hit_at_5']}, mrr={r['reciprocal_rank']}, page_recall={r['page_recall']}")
        for i, hit in enumerate(r['top_hits'][:3]):
            chunk_type = hit.get('chunk_type', hit.get('metadata',{}).get('chunk_type'))
            print(f"  Rank {i+1}: chunk={hit['chunk_id']} type={chunk_type} score={hit['hybrid_score']} rerank={hit.get('rerank_score')} pages={hit['page_numbers']}")
