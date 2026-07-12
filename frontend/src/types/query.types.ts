/**
 * types/query.types.ts
 * ====================
 * TypeScript interfaces for query API request/response types.
 * Mirrors the backend Pydantic schemas exactly.
 */

export interface QueryRequest {
  question: string;
  category_filter?: string | null;
  session_id?: string | null;
}

export interface Citation {
  document_name: string;
  page_number: number;
  category: string;
  excerpt: string;
  rrf_score: number;
  rank: number;
}

export interface QueryResponse {
  query_id: string;
  question: string;
  answer: string;
  summary: string;
  citations: Citation[];
  confidence_score: number;
  llm_provider: string;
  retrieval_count: number;
  response_time_ms: number;
  created_at: string;
}

export interface SearchHistoryEntry {
  search_id: string;
  question: string;
  category_filter: string | null;
  answer_preview: string;
  retrieval_count: number;
  confidence_score: number;
  llm_provider: string;
  response_time_ms: number;
  searched_at: string;
}
