import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { askQuestion, deleteDocument, listDocuments, uploadDocuments } from "./api";
import PdfViewer from "./PdfViewer";
import type { AnswerResponse, Citation, DocumentSummary } from "./types";

function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const [isAnswering, setIsAnswering] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshDocuments();
  }, []);

  async function refreshDocuments() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listDocuments();
      setDocuments(response.documents);
      setSelectedDocument((current) =>
        response.documents.find((document) => document.document_id === current?.document_id)
        ?? response.documents[0]
        ?? null,
      );
    } catch (caughtError) {
      setError(messageFor(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length === 0) return;
    if (files.some((file) => file.type !== "application/pdf" && !file.name.endsWith(".pdf"))) {
      setError("Please select PDF files only.");
      return;
    }
    setIsUploading(true);
    setError(null);
    try {
      const response = await uploadDocuments(files);
      await refreshDocuments();
      setSelectedDocument(response.documents[0] ?? null);
      setAnswer(null);
      setActiveCitation(null);
      setPageNumber(1);
    } catch (caughtError) {
      setError(messageFor(caughtError));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(document: DocumentSummary) {
    setDeletingDocumentId(document.document_id);
    setError(null);
    try {
      await deleteDocument(document.document_id);
      if (selectedDocument?.document_id === document.document_id) {
        setAnswer(null);
        setActiveCitation(null);
        setPageNumber(1);
      }
      await refreshDocuments();
    } catch (caughtError) {
      setError(messageFor(caughtError));
    } finally {
      setDeletingDocumentId(null);
    }
  }

  function openCitation(citation: Citation) {
    setActiveCitation(citation);
    setPageNumber(citation.regions[0]?.page_number ?? citation.page_numbers[0] ?? 1);
  }

  async function handleQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDocument || !question.trim()) return;
    setIsAnswering(true);
    setError(null);
    try {
      setAnswer(await askQuestion(question.trim(), selectedDocument.document_id));
    } catch (caughtError) {
      setError(messageFor(caughtError));
    } finally {
      setIsAnswering(false);
    }
  }

  return (
    <main className="workspace">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">Multimodal Document Intelligence</p>
          <h1>Documents</h1>
        </div>
        <label className="upload-button">
          {isUploading ? "Processing PDFs..." : "Upload PDFs"}
          <input accept="application/pdf,.pdf" disabled={isUploading} multiple onChange={handleFiles} type="file" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="document-list" aria-busy={isLoading}>
          {isLoading && <p>Loading documents...</p>}
          {!isLoading && documents.length === 0 && <p>No PDFs uploaded yet.</p>}
          {documents.map((document) => (
            <div className="document-row" key={document.document_id}>
              <button
                className={document.document_id === selectedDocument?.document_id ? "document active" : "document"}
                onClick={() => {
                  setSelectedDocument(document);
                  setAnswer(null);
                  setActiveCitation(null);
                  setPageNumber(1);
                }}
                type="button"
              >
                <span>{document.filename}</span>
                <small>{document.status} - {document.page_count ?? "?"} pages</small>
              </button>
              <button
                aria-label={`Delete ${document.filename}`}
                className="delete-document"
                disabled={deletingDocumentId === document.document_id}
                onClick={() => void handleDelete(document)}
                title="Delete document"
                type="button"
              >
                {deletingDocumentId === document.document_id ? "…" : "⌫"}
              </button>
            </div>
          ))}
        </div>
      </aside>
      <section className="viewer" aria-label="PDF viewer">
        {selectedDocument ? (
          <>
            <header>
              <div>
                <p className="eyebrow">Source PDF</p>
                <h2>{selectedDocument.filename}</h2>
              </div>
              <span className={`status ${selectedDocument.status}`}>{selectedDocument.status}</span>
            </header>
            {selectedDocument.status === "ready" ? (
              <PdfViewer
                documentId={selectedDocument.document_id}
                highlightedRegions={activeCitation?.regions ?? []}
                onPageChange={setPageNumber}
                pageNumber={pageNumber}
              />
            ) : <div className="empty-state">This document is still being processed.</div>}
          </>
        ) : <div className="empty-state">Upload a PDF to inspect its source pages here.</div>}
      </section>
      <aside className="answers-panel" aria-label="Question answering">
        <div>
          <p className="eyebrow">Grounded answers</p>
          <h2>Ask this document</h2>
        </div>
        <form className="question-form" onSubmit={handleQuestion}>
          <label htmlFor="question">Question</label>
          <textarea
            disabled={!selectedDocument || selectedDocument.status !== "ready" || isAnswering}
            id="question"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a question grounded in this PDF"
            required
            rows={4}
            value={question}
          />
          <button disabled={!selectedDocument || !question.trim() || isAnswering} type="submit">
            {isAnswering ? "Finding evidence..." : "Ask question"}
          </button>
        </form>
        {answer && (
          <section className={`answer ${answer.status}`} aria-live="polite">
            <p className="answer-status">
              {answer.status === "answered" ? "Grounded answer" : "Insufficient evidence"}
            </p>
            <p className="answer-text">{answer.answer}</p>
            {answer.claims.length > 0 && (
              <div className="citation-list">
                {answer.claims.map((claim, index) =>
                  claim.citations.map((citation) => (
                    <button
                      className="citation"
                      key={`${citation.chunk_id}-${index}`}
                      onClick={() => openCitation(citation)}
                      type="button"
                    >
                      {citation.filename ?? citation.document_id}, page {citation.page_numbers.join(", ")}
                    </button>
                  )),
                )}
              </div>
            )}
          </section>
        )}
      </aside>
    </main>
  );
}

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

export default App;
