import asyncio
import json
from app.persistence.vector_index import VectorIndexRepository
from app.retrieval.embeddings import HashedEmbeddingModel
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranking import DeterministicReranker
from app.models.document import DocumentRecord

repo = VectorIndexRepository("C:/Multimodal Document Inteligence/data/app.db")
embedder = HashedEmbeddingModel()
retriever = HybridRetriever(repo, embedder)
reranker = DeterministicReranker()

evals = [
    ("eval-018", "What are the main types of optimization methods used in neural architecture search?", 2, "1908.00709v6.pdf"),
    ("eval-020", "What was the overall execution accuracy of Codex BINDER on the WIKITQ development set?", 5, "2210.02875v2.pdf"),
    ("eval-003", "What datasets were used to train the Transformer, and how large were the English-German and English-French datasets?", 7, "1706.03762v7.pdf"),
    ("eval-007", "What two datasets were used for BERT pre-training?", 2, "1810.04805v2.pdf"),
    ("eval-009", "What was BERTLARGE's F1 score on the SQuAD 1.1 test set when using the ensemble with TriviaQA?", 10, "1810.04805v2.pdf")
]

# Find document IDs
doc_map = {}
for chunk in repo.list_chunks():
    doc_id = chunk["document_id"]
    if doc_id not in doc_map:
        # we don't have filename directly in chunk easily unless we check db, but we can just use the doc_ids
        pass

# We can search globally because the test harness just searches globally or limits by doc id?
# The harness limits by doc_id: `harness.run_benchmark` uses `document_id=doc_id_map[filename]`.
# Let's get doc_ids from the database using sqlite3
import sqlite3
conn = sqlite3.connect("C:/Multimodal Document Inteligence/data/app.db")
c = conn.cursor()
c.execute("SELECT document_id, filename FROM documents")
doc_map = {f: d for d, f in c.fetchall()}
conn.close()

for eid, q, p, f in evals:
    doc_id = doc_map.get(f)
    print(f"\n--- {eid}: {q} (Target: {p}) ---")
    if not doc_id:
        print("Doc not found")
        continue
    hits = retriever.search(q, limit=20, document_id=doc_id)
    ranked = reranker.rerank(q, hits, limit=20)
    
    print("Top 5 Retrieved:")
    found_target = False
    for i, h in enumerate(ranked[:5]):
        print(f"  Rank {i+1}: Page {h.page_numbers} | Final={h.final_score:.4f} (Hyb={h.hybrid_score:.4f}, Sem={h.semantic_score:.4f}, Lex={h.lexical_score:.4f})")
    
    # Check where the target page is
    for i, h in enumerate(ranked):
        if p in h.page_numbers:
            print(f"  --> Target Page {p} found at Rank {i+1}: Final={h.final_score:.4f} (Hyb={h.hybrid_score:.4f}, Sem={h.semantic_score:.4f}, Lex={h.lexical_score:.4f}) | Chunk: {h.chunk_id}")
            break
    else:
        print(f"  --> Target Page {p} NOT found in top 20.")
