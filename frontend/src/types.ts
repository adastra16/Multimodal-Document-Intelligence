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

export type AnswerStatus = "answered" | "insufficient_evidence";

export interface CitationRegion {
  block_id: string;
  page_number: number;
  block_type: string;
  bbox: { x0: number; y0: number; x1: number; y1: number } | null;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  filename: string | null;
  page_numbers: number[];
  source_block_ids: string[];
  regions: CitationRegion[];
}

export interface AnswerClaim {
  text: string;
  citations: Citation[];
}

export interface AnswerResponse {
  question: string;
  status: AnswerStatus;
  answer: string;
  claims: AnswerClaim[];
  evidence_group_ids: string[];
  generation_mode: string;
}

interface DocumentListResponse {
  documents: DocumentSummary[];
}

interface DocumentUploadResponse {
  documents: DocumentSummary[];
}

export type { DocumentListResponse, DocumentUploadResponse };
