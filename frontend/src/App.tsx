import { ChangeEvent, useEffect, useState } from "react";

import { listDocuments, sourceFileUrl, uploadDocuments } from "./api";
import type { DocumentSummary } from "./types";

function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
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
    } catch (caughtError) {
      setError(messageFor(caughtError));
    } finally {
      setIsUploading(false);
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
          {isUploading ? "Processing PDFs…" : "Upload PDFs"}
          <input accept="application/pdf,.pdf" disabled={isUploading} multiple onChange={handleFiles} type="file" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="document-list" aria-busy={isLoading}>
          {isLoading && <p>Loading documents…</p>}
          {!isLoading && documents.length === 0 && <p>No PDFs uploaded yet.</p>}
          {documents.map((document) => (
            <button
              className={document.document_id === selectedDocument?.document_id ? "document active" : "document"}
              key={document.document_id}
              onClick={() => setSelectedDocument(document)}
              type="button"
            >
              <span>{document.filename}</span>
              <small>{document.status} · {document.page_count ?? "?"} pages</small>
            </button>
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
              <iframe
                key={selectedDocument.document_id}
                src={sourceFileUrl(selectedDocument.document_id)}
                title={`PDF source: ${selectedDocument.filename}`}
              />
            ) : (
              <div className="empty-state">This document is still being processed.</div>
            )}
          </>
        ) : (
          <div className="empty-state">Upload a PDF to inspect its source pages here.</div>
        )}
      </section>
    </main>
  );
}

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

export default App;
