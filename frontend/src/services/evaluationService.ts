/**
 * services/evaluationService.ts
 * ==============================
 * API client for the RAG Evaluation Module.
 */

import { apiClient } from './api';

export interface EvaluationResultEntry {
  query: string;
  expected_answer: string;
  generated_answer: string;
  retrieved_document: string;
  expected_document: string;
  retrieved_page: number;
  expected_page: number;
  retrieval_accuracy: number;
  faithfulness: number;
  status: "Pass" | "Fail";
  latency_ms: number;
}

export interface EvaluationReportPayload {
  total_queries: number;
  passed_queries: number;
  failed_queries: number;
  overall_retrieval_accuracy: number;
  overall_faithfulness: number;
  avg_response_time_ms: number;
  evaluated_at: string;
  results: EvaluationResultEntry[];
}

const API_BASE = (import.meta as any).env.VITE_API_BASE_URL ?? '/api/v1';

export const evaluationService = {
  /**
   * Run Golden Set evaluation.
   * Calls POST /evaluate
   */
  runEvaluation: async (limit?: number): Promise<EvaluationReportPayload> => {
    const params = limit ? { limit } : {};
    const response = await apiClient.post('/evaluate', null, { params });
    return response.data.data as EvaluationReportPayload;
  },

  /**
   * Fetch the latest completed evaluation report.
   * Calls GET /evaluate/report/json
   */
  getLatestReport: async (): Promise<EvaluationReportPayload> => {
    const response = await apiClient.get('/evaluate/report/json');
    return response.data.data as EvaluationReportPayload;
  },

  /** Direct download URL for CSV report. */
  downloadCsvUrl: (): string => `${API_BASE}/evaluate/report/csv`,

  /** Direct download URL for Excel report. */
  downloadXlsxUrl: (): string => `${API_BASE}/evaluate/report/xlsx`,
};
