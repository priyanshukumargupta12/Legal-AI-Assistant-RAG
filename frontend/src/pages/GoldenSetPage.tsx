/**
 * pages/GoldenSetPage.tsx
 * ========================
 * Golden Set Management Dashboard.
 *
 * PURPOSE:
 *   Full-featured UI for managing, validating, and analyzing the Golden Set
 *   benchmark dataset used to evaluate the Hybrid RAG pipeline accuracy.
 *
 * SECTIONS:
 *   1. Hero Header        — title, description, action buttons
 *   2. Import Panel       — auto-import button + file upload dropzone
 *   3. Import Progress    — animated progress bar with status messages
 *   4. Statistics Cards   — 6 metric cards (total, valid, invalid, dupes, categories, avg length)
 *   5. Category Chart     — horizontal bar chart for category distribution
 *   6. Validation Report  — collapsible error list grouped by error code
 *   7. Records Table      — paginated table of valid golden records
 *   8. Export Panel       — CSV and XLSX download buttons
 */

import React, { useCallback, useRef, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import {
  AutoAwesome as GoldenIcon,
  CheckCircle as ValidIcon,
  CloudUpload as UploadIcon,
  Download as DownloadIcon,
  Error as ErrorIcon,
  ExpandLess,
  ExpandMore,
  FileUpload as FileUploadIcon,
  InsertDriveFile as FileIcon,
  PieChart as PieIcon,
  PlayArrow as RunIcon,
  Refresh as RefreshIcon,
  Rule as RuleIcon,
  TableChart as TableIcon,
  Warning as WarningIcon,
} from "@mui/icons-material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSnackbar } from "notistack";
import { goldenSetService } from "../services/goldenSetService";
import type {
  CategoryStats,
  FieldValidationError,
  GoldenRecord,
  GoldenSetStatistics,
  ImportResult,
  ValidationReport,
} from "../types/goldenSet";

// ─── Status Chip Colors ─────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, "success" | "error" | "warning" | "default"> = {
  valid: "success",
  invalid: "error",
  duplicate: "warning",
  rejected: "default",
};

// ─── Category Palette ────────────────────────────────────────────────────────

const CATEGORY_COLORS = [
  "#6366f1", // indigo
  "#22d3ee", // cyan
  "#f59e0b", // amber
  "#10b981", // emerald
  "#f43f5e", // rose
  "#a78bfa", // violet
];

// =============================================================================
// STATISTICS CARD COMPONENT
// =============================================================================

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color: string;
  icon: React.ReactNode;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, subtitle, color, icon }) => (
  <Card
    sx={{
      height: "100%",
      border: "1px solid",
      borderColor: "divider",
      background: "linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)",
      transition: "transform 0.2s, box-shadow 0.2s",
      "&:hover": { transform: "translateY(-2px)", boxShadow: 6 },
    }}
  >
    <CardContent sx={{ p: 2.5 }}>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1.5}>
        <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {label}
        </Typography>
        <Avatar sx={{ bgcolor: `${color}22`, width: 36, height: 36 }}>
          <Box sx={{ color, display: "flex", fontSize: 18 }}>{icon}</Box>
        </Avatar>
      </Box>
      <Typography variant="h3" fontWeight={800} sx={{ color, lineHeight: 1, mb: 0.5 }}>
        {value}
      </Typography>
      {subtitle && (
        <Typography variant="caption" color="text.secondary">
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </Card>
);

// =============================================================================
// UPLOAD DROPZONE COMPONENT
// =============================================================================

interface DropzoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

const UploadDropzone: React.FC<DropzoneProps> = ({ onFile, disabled }) => {
  const theme = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
      e.target.value = "";
    },
    [onFile]
  );

  return (
    <Box
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      sx={{
        border: "2px dashed",
        borderColor: isDragging ? "primary.main" : "divider",
        borderRadius: 3,
        p: 4,
        textAlign: "center",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "border-color 0.2s, background 0.2s",
        bgcolor: isDragging ? "primary.main" + "11" : "background.paper",
        "&:hover": !disabled
          ? { borderColor: "primary.main", bgcolor: "primary.main" + "08" }
          : {},
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        style={{ display: "none" }}
        onChange={handleFileChange}
        disabled={disabled}
        id="golden-set-upload-input"
      />
      <FileUploadIcon sx={{ fontSize: 48, color: "primary.main", mb: 1.5, opacity: 0.8 }} />
      <Typography variant="body1" fontWeight={600} gutterBottom>
        Drop your golden set file here
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Supports <strong>CSV</strong> and <strong>Excel (.xlsx)</strong> · Max 50 MB
      </Typography>
      <Button
        variant="outlined"
        size="small"
        sx={{ mt: 2 }}
        disabled={disabled}
        startIcon={<UploadIcon />}
        onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
        id="golden-set-browse-button"
      >
        Browse Files
      </Button>
    </Box>
  );
};

// =============================================================================
// VALIDATION ERRORS PANEL
// =============================================================================

interface ValidationErrorsPanelProps {
  report: ValidationReport;
}

const ValidationErrorsPanel: React.FC<ValidationErrorsPanelProps> = ({ report }) => {
  const [expanded, setExpanded] = useState(false);

  // Group errors by error_code for summary display
  const errorGroups: Record<string, FieldValidationError[]> = {};
  report.errors.forEach((err) => {
    if (!errorGroups[err.error_code]) errorGroups[err.error_code] = [];
    errorGroups[err.error_code].push(err);
  });

  const ERROR_CODE_LABELS: Record<string, string> = {
    MISSING_QUERY: "Missing Query",
    MISSING_ANSWER: "Missing Expected Answer",
    MISSING_SOURCE: "Missing Source Document",
    MISSING_CATEGORY: "Missing Category",
    INVALID_PAGE: "Invalid Page Number",
    UNKNOWN_CATEGORY: "Unknown Category",
    DUPLICATE_QUERY: "Duplicate Query",
  };

  if (report.error_count === 0) {
    return (
      <Alert severity="success" icon={<ValidIcon />} sx={{ borderRadius: 2, mb: 2 }}>
        <Typography fontWeight={600}>All records passed validation!</Typography>
        <Typography variant="body2">
          {report.valid_count} records imported with zero errors.
        </Typography>
      </Alert>
    );
  }

  return (
    <Box>
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        sx={{ cursor: "pointer", mb: 1 }}
        onClick={() => setExpanded(!expanded)}
        id="golden-validation-errors-toggle"
      >
        <Box display="flex" alignItems="center" gap={1}>
          <WarningIcon color="warning" />
          <Typography fontWeight={700}>
            {report.error_count} Validation {report.error_count === 1 ? "Issue" : "Issues"} Found
          </Typography>
          <Chip label={`${report.success_rate.toFixed(1)}% valid`} size="small" color="success" />
        </Box>
        <IconButton size="small">
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      {/* Error code summary chips */}
      <Box display="flex" gap={1} flexWrap="wrap" mb={1}>
        {Object.entries(errorGroups).map(([code, errors]) => (
          <Chip
            key={code}
            label={`${ERROR_CODE_LABELS[code] || code}: ${errors.length}`}
            size="small"
            color="error"
            variant="outlined"
          />
        ))}
      </Box>

      <Collapse in={expanded}>
        <TableContainer
          component={Paper}
          variant="outlined"
          sx={{ maxHeight: 400, borderRadius: 2, mt: 1 }}
        >
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Row</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Field</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Error Code</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Raw Value</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.errors.slice(0, 200).map((err, idx) => (
                <TableRow key={idx} sx={{ "&:hover": { bgcolor: "action.hover" } }}>
                  <TableCell>
                    <Chip label={`Row ${err.row_number}`} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600} color="error.main">
                      {err.field_name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ fontFamily: "monospace", bgcolor: "action.hover", px: 0.8, py: 0.3, borderRadius: 1 }}>
                      {err.error_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{err.error_message}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ maxWidth: 200, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                    >
                      {err.raw_value ?? "—"}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        {report.error_count > 200 && (
          <Typography variant="caption" color="text.secondary" mt={1} display="block">
            Showing first 200 of {report.error_count} errors.
          </Typography>
        )}
      </Collapse>
    </Box>
  );
};

// =============================================================================
// RECORDS TABLE COMPONENT
// =============================================================================

interface RecordsTableProps {
  records: GoldenRecord[];
  total: number;
  validTotal: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const RecordsTable: React.FC<RecordsTableProps> = ({
  records,
  total,
  validTotal,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) => {
  const theme = useTheme();

  const rowBgColor = (status: string) => {
    if (status === "invalid") return theme.palette.mode === "dark" ? "#3a1a1a" : "#fff5f5";
    if (status === "duplicate") return theme.palette.mode === "dark" ? "#3a3a1a" : "#fffde7";
    return "inherit";
  };

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Box display="flex" alignItems="center" gap={1}>
          <TableIcon color="primary" />
          <Typography variant="h6" fontWeight={700}>
            Golden Records
          </Typography>
          <Chip label={`${validTotal} valid`} size="small" color="success" />
        </Box>
        <Typography variant="body2" color="text.secondary">
          Showing {records.length} of {total} records
        </Typography>
      </Box>

      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{ borderRadius: 2, maxHeight: 500 }}
      >
        <Table size="small" stickyHeader id="golden-records-table">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, width: 60 }}>Row</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 260 }}>Query</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 240 }}>Expected Answer</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 160 }}>Source Document</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 60 }}>Page</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 130 }}>Category</TableCell>
              <TableCell sx={{ fontWeight: 700, width: 90 }}>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {records.map((rec, idx) => (
              <TableRow
                key={`${rec.row_number}-${idx}`}
                sx={{ bgcolor: rowBgColor(rec.status), "&:hover": { filter: "brightness(0.97)" } }}
              >
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    #{rec.row_number}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Tooltip title={rec.query} placement="top-start">
                    <Typography
                      variant="body2"
                      sx={{
                        maxWidth: 250,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {rec.query}
                    </Typography>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Tooltip title={rec.expected_answer} placement="top-start">
                    <Typography
                      variant="body2"
                      sx={{
                        maxWidth: 230,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: "text.secondary",
                      }}
                    >
                      {rec.expected_answer}
                    </Typography>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" fontWeight={500} color="info.main">
                    {rec.source_document}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip label={rec.page_number} size="small" variant="outlined" />
                </TableCell>
                <TableCell>
                  <Chip
                    label={rec.category}
                    size="small"
                    sx={{ fontSize: "0.68rem" }}
                    variant="outlined"
                    color="secondary"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={rec.status}
                    size="small"
                    color={STATUS_COLORS[rec.status] || "default"}
                  />
                </TableCell>
              </TableRow>
            ))}
            {records.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} sx={{ textAlign: "center", py: 4 }}>
                  <Typography color="text.secondary">No records found.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={total}
        page={page - 1}
        rowsPerPage={pageSize}
        rowsPerPageOptions={[25, 50, 100, 200]}
        onPageChange={(_, newPage) => onPageChange(newPage + 1)}
        onRowsPerPageChange={(e) => onPageSizeChange(parseInt(e.target.value, 10))}
        id="golden-records-pagination"
      />
    </Box>
  );
};

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

const GoldenSetPage: React.FC = () => {
  const theme = useTheme();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  // ── Local State ─────────────────────────────────────────────────────────────
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [recordsPage, setRecordsPage] = useState(1);
  const [recordsPageSize, setRecordsPageSize] = useState(50);

  // ── Queries ─────────────────────────────────────────────────────────────────
  const { data: persistedStats, isLoading: statsLoading } = useQuery({
    queryKey: ["golden-statistics"],
    queryFn: goldenSetService.getStatistics,
    retry: false,
  });

  const { data: persistedReport, isLoading: reportLoading } = useQuery({
    queryKey: ["golden-report"],
    queryFn: goldenSetService.getReport,
    retry: false,
  });

  const { data: recordsList, isLoading: recordsLoading } = useQuery({
    queryKey: ["golden-records", recordsPage, recordsPageSize],
    queryFn: () => goldenSetService.getRecords(recordsPage, recordsPageSize),
    retry: false,
    enabled: !!(importResult || persistedStats),
  });

  // ── Mutations ────────────────────────────────────────────────────────────────
  const autoImportMutation = useMutation({
    mutationFn: goldenSetService.autoImport,
    onSuccess: (data) => {
      setImportResult(data);
      queryClient.invalidateQueries({ queryKey: ["golden-statistics"] });
      queryClient.invalidateQueries({ queryKey: ["golden-report"] });
      queryClient.invalidateQueries({ queryKey: ["golden-records"] });
      enqueueSnackbar(
        `Import complete: ${data.statistics.valid_queries}/${data.statistics.total_queries} records valid.`,
        { variant: "success" }
      );
    },
    onError: () => {
      enqueueSnackbar("Auto-import failed. Check that golden_set.csv exists in the metadata/ directory.", {
        variant: "error",
      });
    },
  });

  // ── File Upload Handler ──────────────────────────────────────────────────────
  const handleFileUpload = useCallback(
    async (file: File) => {
      const suffix = file.name.split(".").pop()?.toLowerCase();
      if (!suffix || !["csv", "xlsx"].includes(suffix)) {
        enqueueSnackbar("Unsupported file type. Please upload a .csv or .xlsx file.", {
          variant: "warning",
        });
        return;
      }

      setIsUploading(true);
      setUploadProgress(0);

      try {
        const result = await goldenSetService.uploadFile(file, setUploadProgress);
        setImportResult(result);
        queryClient.invalidateQueries({ queryKey: ["golden-statistics"] });
        queryClient.invalidateQueries({ queryKey: ["golden-report"] });
        queryClient.invalidateQueries({ queryKey: ["golden-records"] });
        enqueueSnackbar(
          `Upload successful: ${result.statistics.valid_queries}/${result.statistics.total_queries} valid records.`,
          { variant: "success" }
        );
      } catch {
        enqueueSnackbar("Upload failed. Please check the file format and try again.", {
          variant: "error",
        });
      } finally {
        setIsUploading(false);
        setUploadProgress(0);
      }
    },
    [enqueueSnackbar, queryClient]
  );

  // ── Derived data ─────────────────────────────────────────────────────────────
  const activeStats = importResult?.statistics ?? persistedStats;
  const activeReport = importResult?.validation_report ?? persistedReport;
  const isImporting = autoImportMutation.isPending;
  const isBusy = isImporting || isUploading;

  // Category chart data
  const categoryChartData = activeStats
    ? Object.entries(activeStats.category_distribution).map(([name, count]) => ({
        name,
        count,
      }))
    : [];

  return (
    <Box>
      {/* ── PAGE HEADER ─────────────────────────────────────────────────────── */}
      <Box mb={4}>
        <Box display="flex" alignItems="center" gap={1.5} mb={1}>
          <Avatar sx={{ bgcolor: "primary.main", width: 44, height: 44 }}>
            <GoldenIcon />
          </Avatar>
          <Box>
            <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: "-0.03em", lineHeight: 1.1 }}>
              Golden Set Management
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Import, validate, and analyze the benchmark dataset used to evaluate the Hybrid RAG pipeline.
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* ── IMPORT PANEL ─────────────────────────────────────────────────────── */}
      <Grid container spacing={3} mb={4}>
        {/* Auto-import card */}
        <Grid item xs={12} md={5}>
          <Card sx={{ height: "100%", border: "1px solid", borderColor: "divider" }}>
            <CardContent sx={{ p: 3 }}>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <RunIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Auto-Import
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Automatically detect and import <strong>golden_set.csv</strong> or{" "}
                <strong>golden_set.xlsx</strong> from the metadata directory. The pipeline reads,
                validates, computes statistics, maps sources, and exports validated files.
              </Typography>

              <Button
                variant="contained"
                size="large"
                fullWidth
                startIcon={isImporting ? <CircularProgress size={18} color="inherit" /> : <RunIcon />}
                onClick={() => autoImportMutation.mutate()}
                disabled={isBusy}
                id="golden-auto-import-button"
                sx={{
                  py: 1.5,
                  fontWeight: 700,
                  fontSize: "1rem",
                  background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
                  "&:hover": {
                    background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
                  },
                }}
              >
                {isImporting ? "Importing..." : "Run Auto-Import"}
              </Button>

              {isImporting && (
                <Box mt={2}>
                  <LinearProgress
                    sx={{ borderRadius: 2, height: 6 }}
                    id="golden-import-progress"
                  />
                  <Typography variant="caption" color="text.secondary" mt={0.5} display="block" textAlign="center">
                    Reading → Validating → Computing Statistics → Exporting...
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Upload dropzone card */}
        <Grid item xs={12} md={7}>
          <Card sx={{ height: "100%", border: "1px solid", borderColor: "divider" }}>
            <CardContent sx={{ p: 3 }}>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <UploadIcon color="secondary" />
                <Typography variant="h6" fontWeight={700}>
                  Upload Custom File
                </Typography>
              </Box>

              <UploadDropzone onFile={handleFileUpload} disabled={isBusy} />

              {isUploading && (
                <Box mt={2}>
                  <Box display="flex" justifyContent="space-between" mb={0.5}>
                    <Typography variant="caption" color="text.secondary">
                      Uploading...
                    </Typography>
                    <Typography variant="caption" fontWeight={700} color="primary.main">
                      {uploadProgress}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={uploadProgress}
                    sx={{ borderRadius: 2, height: 6 }}
                    id="golden-upload-progress"
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* ── LOADING STATES ───────────────────────────────────────────────────── */}
      {(statsLoading || reportLoading) && !importResult && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress />
        </Box>
      )}

      {/* ── EMPTY STATE (no import yet) ───────────────────────────────────────── */}
      {!activeStats && !isBusy && !statsLoading && !reportLoading && (
        <Alert
          severity="info"
          icon={<GoldenIcon />}
          sx={{ mb: 4, borderRadius: 2 }}
          id="golden-empty-state"
        >
          <Typography fontWeight={600}>No golden set imported yet.</Typography>
          <Typography variant="body2">
            Click <strong>Run Auto-Import</strong> above to import the golden set from the
            metadata directory, or upload a custom file.
          </Typography>
        </Alert>
      )}

      {/* ── STATISTICS DASHBOARD ─────────────────────────────────────────────── */}
      {activeStats && (
        <>
          <Box display="flex" alignItems="center" gap={1} mb={2.5}>
            <PieIcon color="primary" />
            <Typography variant="h5" fontWeight={700}>
              Statistics Dashboard
            </Typography>
            <Chip
              label={activeStats.source_file}
              size="small"
              icon={<FileIcon sx={{ fontSize: "0.85rem !important" }} />}
              variant="outlined"
            />
          </Box>

          {/* 6 Stats Cards */}
          <Grid container spacing={2.5} mb={4}>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Total Queries"
                value={activeStats.total_queries}
                subtitle="all records"
                color={theme.palette.primary.main}
                icon={<GoldenIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Valid"
                value={activeStats.valid_queries}
                subtitle={`${activeStats.valid_percentage.toFixed(1)}% pass rate`}
                color={theme.palette.success.main}
                icon={<ValidIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Invalid"
                value={activeStats.invalid_queries}
                subtitle="field violations"
                color={theme.palette.error.main}
                icon={<ErrorIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Duplicates"
                value={activeStats.duplicate_queries}
                subtitle="duplicate queries"
                color={theme.palette.warning.main}
                icon={<WarningIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Categories"
                value={Object.keys(activeStats.category_distribution).length}
                subtitle="distinct categories"
                color={theme.palette.info.main}
                icon={<RuleIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <StatCard
                label="Avg Query Len"
                value={`${Math.round(activeStats.avg_query_length)} ch`}
                subtitle="characters per query"
                color="#8b5cf6"
                icon={<FileIcon fontSize="small" />}
              />
            </Grid>
          </Grid>

          {/* Category Distribution Chart */}
          {categoryChartData.length > 0 && (
            <Card sx={{ mb: 4, border: "1px solid", borderColor: "divider" }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" fontWeight={700} mb={3}>
                  Category Distribution (Valid Records)
                </Typography>
                <Box height={220}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={categoryChartData}
                      layout="vertical"
                      margin={{ top: 0, right: 30, left: 20, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" opacity={0.1} horizontal={false} />
                      <XAxis type="number" fontSize={11} />
                      <YAxis type="category" dataKey="name" width={130} fontSize={11} fontWeight={600} />
                      <ChartTooltip
                        formatter={(value: number) => [value, "Records"]}
                        contentStyle={{
                          background: theme.palette.background.paper,
                          border: `1px solid ${theme.palette.divider}`,
                          borderRadius: 8,
                        }}
                      />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={28} id="golden-category-chart-bar">
                        {categoryChartData.map((_, index) => (
                          <Cell
                            key={index}
                            fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Box>

                {/* Category Chips */}
                <Box display="flex" gap={1} flexWrap="wrap" mt={2} pt={2} borderTop="1px solid" sx={{ borderColor: "divider" }}>
                  {activeStats.category_stats.map((cs: CategoryStats, idx) => (
                    <Chip
                      key={cs.category}
                      label={`${cs.category}: ${cs.valid} valid / ${cs.total} total`}
                      size="small"
                      sx={{
                        bgcolor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] + "22",
                        color: CATEGORY_COLORS[idx % CATEGORY_COLORS.length],
                        fontWeight: 600,
                        borderColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] + "55",
                        border: "1px solid",
                      }}
                    />
                  ))}
                </Box>

                {/* Additional stats row */}
                <Box display="flex" gap={4} mt={2.5} pt={2} borderTop="1px solid" sx={{ borderColor: "divider" }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: "uppercase" }}>
                      Avg Answer Length
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {Math.round(activeStats.avg_answer_length)} chars
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: "uppercase" }}>
                      Unique Source Docs
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {activeStats.unique_source_docs}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: "uppercase" }}>
                      Computed At
                    </Typography>
                    <Typography variant="body1" fontWeight={700}>
                      {new Date(activeStats.computed_at).toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* ── VALIDATION REPORT ────────────────────────────────────────────────── */}
      {activeReport && (
        <Card sx={{ mb: 4, border: "1px solid", borderColor: "divider" }}>
          <CardContent sx={{ p: 3 }}>
            <Box display="flex" alignItems="center" gap={1} mb={2.5}>
              <RuleIcon color="primary" />
              <Typography variant="h6" fontWeight={700}>
                Validation Report
              </Typography>
              <Chip label={activeReport.source_file} size="small" variant="outlined" />
            </Box>
            <ValidationErrorsPanel report={activeReport} />
          </CardContent>
        </Card>
      )}

      {/* ── RECORDS TABLE ────────────────────────────────────────────────────── */}
      {(recordsList || recordsLoading) && activeStats && (
        <Card sx={{ mb: 4, border: "1px solid", borderColor: "divider" }}>
          <CardContent sx={{ p: 3 }}>
            {recordsLoading ? (
              <Box display="flex" justifyContent="center" py={4}>
                <CircularProgress />
              </Box>
            ) : recordsList ? (
              <RecordsTable
                records={recordsList.records}
                total={recordsList.total}
                validTotal={recordsList.valid_total}
                page={recordsPage}
                pageSize={recordsPageSize}
                onPageChange={(p) => { setRecordsPage(p); queryClient.invalidateQueries({ queryKey: ["golden-records"] }); }}
                onPageSizeChange={(s) => { setRecordsPageSize(s); setRecordsPage(1); queryClient.invalidateQueries({ queryKey: ["golden-records"] }); }}
              />
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* ── EXPORT PANEL ─────────────────────────────────────────────────────── */}
      {activeStats && (
        <Card sx={{ border: "1px solid", borderColor: "divider" }}>
          <CardContent sx={{ p: 3 }}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <DownloadIcon color="primary" />
              <Typography variant="h6" fontWeight={700}>
                Export Validated Golden Set
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Download the validated golden set with status annotations. Valid rows are green,
              invalid rows are red, and duplicate rows are orange in the Excel export.
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap">
              <Button
                variant="contained"
                size="large"
                startIcon={<DownloadIcon />}
                onClick={() => window.open(goldenSetService.downloadCsvUrl(), "_blank")}
                id="golden-export-csv-button"
                sx={{
                  fontWeight: 700,
                  background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                  "&:hover": { background: "linear-gradient(135deg, #059669 0%, #047857 100%)" },
                }}
              >
                Download Validated CSV
              </Button>
              <Button
                variant="contained"
                size="large"
                startIcon={<DownloadIcon />}
                onClick={() => window.open(goldenSetService.downloadXlsxUrl(), "_blank")}
                id="golden-export-xlsx-button"
                sx={{
                  fontWeight: 700,
                  background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                  "&:hover": { background: "linear-gradient(135deg, #d97706 0%, #b45309 100%)" },
                }}
              >
                Download Validated XLSX
              </Button>
              <Button
                variant="outlined"
                size="large"
                startIcon={<RefreshIcon />}
                onClick={() => autoImportMutation.mutate()}
                disabled={isBusy}
                id="golden-reimport-button"
              >
                Re-Import
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default GoldenSetPage;
