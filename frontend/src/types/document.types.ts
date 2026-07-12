/**
 * types/document.types.ts
 * ========================
 * TypeScript interfaces for document management API types.
 */

export type DocumentCategory = 'Acts' | 'CourtJudgement' | 'Tax' | 'Legal_opinion';
export type DocumentStatus = 'valid' | 'invalid' | 'duplicate';

export interface DocumentListItem {
  document_id: string;
  file_name: string;
  category: DocumentCategory;
  file_size_bytes: number;
  page_count: number;
  status: DocumentStatus;
  ingested_at: string;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentListItem[];
}

export interface DocumentUploadResponse {
  document_id: string;
  file_name: string;
  category: DocumentCategory;
  page_count: number;
  chunk_count: number;
  message: string;
}

export interface DatasetStatistics {
  total_pdfs: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  acts_count: number;
  court_count: number;
  tax_count: number;
  legal_opinion_count: number;
  avg_pages: number;
  scanned_at: string;
  message: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  services: Record<string, string>;
  timestamp: string;
}

export interface ApiError {
  error: string;
  message: string;
  detail: Record<string, unknown>;
  timestamp: string;
}
