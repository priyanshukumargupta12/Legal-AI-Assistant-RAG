/**
 * types/evaluation.types.ts
 * ==========================
 * TypeScript interfaces for evaluation pipeline API types.
 */

export interface EvaluationResultItem {
  question: string;
  expected_answer: string;
  generated_answer: string;
  expected_doc: string;
  expected_page: number;
  retrieved_correctly: boolean;
  precision_at_k: number;
  recall_at_k: number;
  faithfulness: number;
  context_precision: number;
  context_recall: number;
  answer_relevancy: number;
  response_time_ms: number;
}

export interface EvaluationReportResponse {
  run_id: string;
  golden_set_file: string;
  total_questions: number;
  llm_provider: string;
  avg_precision_at_k: number;
  avg_recall_at_k: number;
  avg_faithfulness: number;
  avg_context_precision: number;
  avg_context_recall: number;
  avg_answer_relevancy: number;
  correct_retrieval_rate: number;
  results: EvaluationResultItem[];
  run_at: string;
}

export interface GoldenSetImportResponse {
  file_name: string;
  total_entries: number;
  valid_entries: number;
  invalid_entries: number;
  message: string;
}
