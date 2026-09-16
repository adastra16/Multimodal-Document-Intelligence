import type { AnswerResponse, DocumentListResponse, DocumentUploadResponse } from "./types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents");
}

export function uploadDocuments(files: File[]): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return request<DocumentUploadResponse>("/documents", { method: "POST", body: formData });
}

export function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`/documents/${documentId}`, { method: "DELETE" });
}

export function sourceFileUrl(documentId: string): string {
  return `${apiBaseUrl}/documents/${documentId}/file`;
}

export function askQuestion(question: string, documentId: string): Promise<AnswerResponse> {
  return request<AnswerResponse>("/answers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, document_id: documentId }),
  });
}
