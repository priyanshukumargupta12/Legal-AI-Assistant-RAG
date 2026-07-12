/**
 * services/goldenSetService.ts
 * ==============================
 * API client for the Golden Set Management Module.
 *
 * PURPOSE:
 *   Provides typed functions for all /api/v1/golden/* endpoints.
 *   Every function returns the data payload (unwrapped from StandardResponse).
 *
 * ENDPOINTS:
 *   autoImport()       — POST /golden/import
 *   uploadFile()       — POST /golden/upload (multipart)
 *   getStatistics()    — GET  /golden/statistics
 *   getReport()        — GET  /golden/report
 *   getRecords()       — GET  /golden/records (paginated)
 *   downloadCsvUrl()   — URL string for CSV download
 *   downloadXlsxUrl()  — URL string for XLSX download
 */

import { apiClient } from './api';
import type {
  ImportResult,
  GoldenSetStatistics,
  ValidationReport,
  GoldenRecordsList,
} from '../types/goldenSet';

// Base URL for direct download links
const API_BASE = (import.meta as any).env.VITE_API_BASE_URL ?? '/api/v1';

export const goldenSetService = {
  /**
   * Trigger automatic import of golden_set.csv or golden_set.xlsx
   * from the backend metadata/ directory.
   */
  autoImport: async (): Promise<ImportResult> => {
    const response = await apiClient.post('/golden/import');
    return response.data.data as ImportResult;
  },

  /**
   * Upload a custom golden set file (CSV or XLSX).
   * Uses FormData for multipart/form-data upload.
   *
   * @param file - File object selected by the user
   * @param onUploadProgress - Optional callback for upload progress (0-100)
   */
  uploadFile: async (
    file: File,
    onUploadProgress?: (percent: number) => void
  ): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/golden/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000, // 2 min timeout for large files
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onUploadProgress(percent);
        }
      },
    });
    return response.data.data as ImportResult;
  },

  /**
   * Return the golden set statistics from the last import.
   */
  getStatistics: async (): Promise<GoldenSetStatistics> => {
    const response = await apiClient.get('/golden/statistics');
    return response.data.data as GoldenSetStatistics;
  },

  /**
   * Return the full validation report from the last import.
   */
  getReport: async (): Promise<ValidationReport> => {
    const response = await apiClient.get('/golden/report');
    return response.data.data as ValidationReport;
  },

  /**
   * Return a paginated list of validated golden records.
   *
   * @param page      - Page number (1-based)
   * @param pageSize  - Records per page (max 200)
   * @param category  - Optional category filter
   * @param status    - Optional status filter
   */
  getRecords: async (
    page = 1,
    pageSize = 50,
    category?: string,
    status?: string
  ): Promise<GoldenRecordsList> => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (category) params.category = category;
    if (status) params.status = status;
    const response = await apiClient.get('/golden/records', { params });
    return response.data.data as GoldenRecordsList;
  },

  /** Direct download URL for validated CSV (used via window.open or anchor). */
  downloadCsvUrl: (): string => `${API_BASE}/golden/export/csv`,

  /** Direct download URL for validated XLSX (used via window.open or anchor). */
  downloadXlsxUrl: (): string => `${API_BASE}/golden/export/xlsx`,
};
