export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface DocumentSummary {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  created_at: string;
  updated_at: string;
}

interface DocumentListResponse {
  documents: DocumentSummary[];
}

interface DocumentUploadResponse {
  documents: DocumentSummary[];
}

export type { DocumentListResponse, DocumentUploadResponse };
