/**
 * types/goldenSet.ts
 * ===================
 * TypeScript interfaces for the Golden Set Management Module.
 *
 * PURPOSE:
 *   Defines all TypeScript types that correspond to the backend
 *   Pydantic schemas for /api/v1/golden/* endpoints.
 */

// ─── Field Validation Error ─────────────────────────────────────────────────

export interface FieldValidationError {
  row_number: number;
  field_name: string;
  error_code: string;
  error_message: string;
  raw_value: string | null;
}

// ─── Golden Record ───────────────────────────────────────────────────────────

export interface GoldenRecord {
  row_number: number;
  query: string;
  expected_answer: string;
  source_document: string;
  page_number: number;
  category: string;
  citation: string | null;
  difficulty: string | null;
  tags: string | null;
  notes: string | null;
  status: "valid" | "invalid" | "duplicate" | "rejected";
  query_length: number;
  answer_length: number;
  validation_errors: FieldValidationError[];
}

// ─── Validation Report ───────────────────────────────────────────────────────

export interface ValidationReport {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  rejected_count: number;
  error_count: number;
  success_rate: number;
  source_file: string;
  validated_at: string;
  errors: FieldValidationError[];
}

// ─── Category Stats ──────────────────────────────────────────────────────────

export interface CategoryStats {
  category: string;
  total: number;
  valid: number;
  invalid: number;
  duplicate: number;
  avg_query_len: number;
}

// ─── Source Mapping ──────────────────────────────────────────────────────────

export interface SourceMapping {
  source_document: string;
  document_id: string | null;
  category: string | null;
  page_count: number | null;
  is_indexed: boolean;
}

// ─── Golden Set Statistics ───────────────────────────────────────────────────

export interface GoldenSetStatistics {
  total_queries: number;
  valid_queries: number;
  invalid_queries: number;
  duplicate_queries: number;
  rejected_queries: number;
  valid_percentage: number;
  category_distribution: Record<string, number>;
  category_stats: CategoryStats[];
  avg_query_length: number;
  avg_answer_length: number;
  unique_source_docs: number;
  source_file: string;
  computed_at: string;
}

// ─── Import Result ───────────────────────────────────────────────────────────

export interface ImportResult {
  source_file_name: string;
  import_duration_s: number;
  statistics: GoldenSetStatistics;
  validation_report: ValidationReport;
  source_mappings: SourceMapping[];
  message: string;
}

// ─── Records List ────────────────────────────────────────────────────────────

export interface GoldenRecordsList {
  total: number;
  valid_total: number;
  page: number;
  page_size: number;
  total_pages: number;
  records: GoldenRecord[];
  category_filter: string | null;
  status_filter: string | null;
}
