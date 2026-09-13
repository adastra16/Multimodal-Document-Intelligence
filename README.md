# Multimodal Document Intelligence

A production-grade, multimodal document intelligence system capable of parsing visually rich PDFs (multi-column, tables, figures, scanned/OCR), performing cross-page hybrid retrieval, generating strictly grounded answers, and providing interactive bounding-box citations in a web UI.

## Features

- **Multimodal PDF Ingestion**: Extracts text, tables, and figures along with their precise coordinates `(x0, y0, x1, y1)` and page numbers. Includes fallback OCR for scanned documents.
- **Hybrid Search**: Combines sparse keyword search with dense semantic embeddings to maximize retrieval recall.
- **Cross-Page Context Expansion**: Seeds the highest-scoring chunks and expands them into adjacent or structurally related chunks, ensuring that the LLM has contiguous context even when a thought spans multiple pages.
- **Visual Citations**: Answers are grounded with exact visual provenance. Users can click on a citation in the frontend to jump directly to the bounding box on the original PDF page.
- **Strict Anti-Hallucination**: Employs deterministic salient-term reranking to filter out chunks matching only stop words, coupled with a calibrated refusal threshold. If evidence is insufficient, the system explicitly refuses to answer rather than hallucinating.

## Evaluation Results

Based on our benchmark harness, the system achieves:
- **Cross-Page Recall**: 100%
- **Hallucination Rate on Unanswerable Queries**: ~0.0% (down from 25% due to salient term reranking)
- **Status Accuracy**: 100.0%

## Quickstart (Docker)

You can run the entire stack (Backend + Frontend) using Docker Compose:

```bash
docker-compose up -d --build
```
- The backend API will be available at `http://localhost:8000`.
- The frontend web UI will be available at `http://localhost:3000`.

## Local Development

If you prefer to run the system locally without Docker:

### Backend
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
2. Run the development server:
   ```bash
   make run
   # Or directly: python -m uvicorn app.main:app --reload --app-dir backend
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies and start the Vite dev server:
   ```bash
   npm install
   npm run dev
   ```

## Architecture

For more details on the retrieval and provenance architecture, please read our [Architecture Decision Record (ADR)](docs/adr/0001-cross-page-retrieval-and-provenance.md).
