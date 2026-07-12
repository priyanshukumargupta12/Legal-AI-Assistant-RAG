/**
 * utils/helpers.ts
 * ================
 * Shared utility functions for the frontend.
 */

/** Format bytes to human-readable string (e.g., '4.2 MB'). */
export const formatBytes = (bytes: number, decimals = 2): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
};

/** Format milliseconds to human-readable string. */
export const formatLatency = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

/** Format a 0-1 score as a percentage string. */
export const formatScore = (score: number): string =>
  `${(score * 100).toFixed(1)}%`;

/** Format an ISO datetime string to a local date-time. */
export const formatDateTime = (isoString: string): string => {
  return new Date(isoString).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

/** Map a document category key to a display label. */
export const getCategoryLabel = (category: string): string => {
  const labels: Record<string, string> = {
    Acts: 'Acts & Statutes',
    CourtJudgement: 'Court Judgments',
    Tax: 'Tax Documents',
    Legal_opinion: 'Legal Opinions',
  };
  return labels[category] ?? category;
};

/** Get a MUI color name for a document category. */
export const getCategoryColor = (category: string): 'primary' | 'secondary' | 'success' | 'warning' => {
  const colors: Record<string, 'primary' | 'secondary' | 'success' | 'warning'> = {
    Acts: 'primary',
    CourtJudgement: 'secondary',
    Tax: 'success',
    Legal_opinion: 'warning',
  };
  return colors[category] ?? 'primary';
};
