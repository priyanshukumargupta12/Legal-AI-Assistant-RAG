import { apiClient } from './api';
import type { QueryRequest } from '../types/query.types';

export interface CitationPayload {
  document: string;
  page: number;
  category: string;
  snippet?: string;
  // Fallbacks for frontend component matching
  document_name?: string;
  page_number?: number;
}

export interface RetrievedChunkPayload {
  chunk_id: string;
  document: string;
  page: number;
  category: string;
  text: string;
  hybrid_score: number;
}

export interface QueryResponsePayload {
  answer: string;
  summary: string;
  citations: CitationPayload[];
  confidence_score: number;
  retrieval_time_ms: number;
  retrieved_chunks?: RetrievedChunkPayload[];
}

export interface SearchResultPayload {
  chunk_id: string;
  document: string;
  page: number;
  category: string;
  text: string;
  vector_score: number;
  bm25_score: number;
  hybrid_score: number;
}

export interface SearchResponsePayload {
  query: string;
  results: SearchResultPayload[];
  vector_count: number;
  bm25_count: number;
  total_candidates: number;
  retrieval_time_ms: number;
}

export interface HistoryItemPayload {
  question: string;
  answer: string;
  timestamp: string;
}

export const queryService = {
  /** Submit a legal question to the hybrid RAG pipeline (calls POST /query). */
  submitQuery: async (request: QueryRequest): Promise<QueryResponsePayload> => {
    // request has query (frontend) but backend expects query. 
    // Wait, query.types.ts has question or query? Let's check query.types.ts
    // QueryRequest has query: string, category_filter: string
    // Let's pass the parameters mapping:
    const payload = {
      query: request.question || (request as any).query, // handle both fields for robustness
      category_filter: request.category_filter || null,
    };
    const response = await apiClient.post('/query', payload);
    return response.data.data;
  },

  /** Submit a semantic/keyword search query (calls POST /search). */
  submitSearch: async (
    query: string,
    categoryFilter?: string | null,
    topK: number = 10
  ): Promise<SearchResponsePayload> => {
    const payload = {
      query,
      category_filter: categoryFilter === 'All' ? null : (categoryFilter || null),
      top_k: topK,
    };
    const response = await apiClient.post('/search', payload);
    return response.data.data;
  },

  /** Fetch QA chat history (calls GET /history). */
  getSearchHistory: async (): Promise<HistoryItemPayload[]> => {
    const response = await apiClient.get('/history');
    return response.data.data;
  },
};
