/**
 * pages/EvaluationPage.tsx
 * ========================
 * RAG Pipeline Evaluation Dashboard.
 */

import React, { useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Assessment as EvalIcon,
  PlayArrow as StartIcon,
  Download as DownloadIcon,
  Speed as LatencyIcon,
  CheckCircle as PassedIcon,
  Cancel as FailedIcon,
  Percent as PercentIcon,
} from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSnackbar } from "notistack";
import { evaluationService } from "../services/evaluationService";

// Status Chip Colors
const STATUS_COLORS: Record<string, "success" | "warning" | "error" | "default"> = {
  Pass: "success",
  "Partial Match": "warning",
  Fail: "error",
};

// Stat Card Component
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
      <Typography variant="h4" fontWeight={800} sx={{ color, lineHeight: 1, mb: 0.5 }}>
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

const EvaluationPage: React.FC = () => {
  const theme = useTheme();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const [limit, setLimit] = useState<number>(0); // 0 means run all
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Load the latest evaluation report on page load
  const { data: latestReport, isLoading: reportLoading } = useQuery({
    queryKey: ["latest-eval-report"],
    queryFn: evaluationService.getLatestReport,
    retry: false,
  });

  // Mutation: Trigger RAG pipeline evaluation
  const runEvalMutation = useMutation({
    mutationFn: (runLimit?: number) => evaluationService.runEvaluation(runLimit),
    onSuccess: (data) => {
      queryClient.setQueryData(["latest-eval-report"], data);
      enqueueSnackbar(`Evaluation complete: ${data.passed_queries}/${data.total_queries} queries passed.`, {
        variant: "success",
      });
    },
    onError: (err: any) => {
      enqueueSnackbar(`Evaluation failed: ${err.message || "Unknown error"}`, {
        variant: "error",
      });
    },
  });

  const isBusy = runEvalMutation.isPending;

  const handleRunEvaluation = () => {
    const runLimit = limit > 0 ? limit : undefined;
    runEvalMutation.mutate(runLimit);
  };

  // Setup data format for Bar Chart
  const chartData = latestReport
    ? [
        { name: "Retrieval Accuracy", score: latestReport.overall_retrieval_accuracy * 100 },
        { name: "Faithfulness", score: latestReport.overall_faithfulness * 100 },
      ]
    : [];

  const results = latestReport?.results || [];
  const totalResults = results.length;
  
  // Paginate table rows
  const paginatedResults = results.slice((page - 1) * pageSize, page * pageSize);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "N/A";
    const day = d.getDate();
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = months[d.getMonth()];
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    let tz = "UTC";
    try {
      const tzStr = d.toLocaleTimeString('en-US', { timeZoneName: 'short' });
      const parts = tzStr.split(' ');
      if (parts.length > 0) {
        tz = parts[parts.length - 1];
      }
    } catch (e) {}
    return `${day} ${month} ${year} ${hours}:${minutes} ${tz}`;
  };

  return (
    <Box>
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <Box mb={4} display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: "-0.03em", mb: 0.5 }}>
            RAG Evaluation Dashboard
          </Typography>
          <Typography color="text.secondary" variant="body2">
            Measure retrieval accuracy and faithfulness metrics using the ground truth Golden Set.
          </Typography>
        </Box>
        <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="eval-limit-label">Limit Queries</InputLabel>
            <Select
              labelId="eval-limit-label"
              id="eval-limit-select"
              value={limit}
              label="Limit Queries"
              onChange={(e) => setLimit(Number(e.target.value))}
              disabled={isBusy}
            >
              <MenuItem value={0}>Run All Queries</MenuItem>
              <MenuItem value={5}>Run 5 Queries</MenuItem>
              <MenuItem value={10}>Run 10 Queries</MenuItem>
              <MenuItem value={25}>Run 25 Queries</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            color="primary"
            startIcon={isBusy ? <CircularProgress size={18} color="inherit" /> : <StartIcon />}
            onClick={handleRunEvaluation}
            disabled={isBusy}
            id="golden-run-evaluation-button"
            sx={{
              fontWeight: 700,
              background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
              "&:hover": { background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)" },
            }}
          >
            {isBusy ? "Evaluating..." : "Run Evaluation"}
          </Button>
        </Box>
      </Box>

      {/* ── RUNNING OR LOADING STATE ─────────────────────────────────────── */}
      {isBusy && (
        <Card sx={{ p: 4, textAlign: "center", mb: 4, border: "1px solid", borderColor: "divider" }}>
          <CircularProgress size={40} sx={{ mb: 2 }} />
          <Typography variant="h6" fontWeight={700}>
            Running Pipeline Evaluation
          </Typography>
          <Typography variant="body2" color="text.secondary" mt={0.5}>
            Firing hybrid retrieval and verifying LLM generation correctness. This may take a minute...
          </Typography>
        </Card>
      )}

      {/* ── INACTIVE STATE ────────────────────────────────────────────────── */}
      {!latestReport && !isBusy && !reportLoading && (
        <Alert severity="info" sx={{ mb: 4, borderRadius: 2 }} icon={<EvalIcon />}>
          No evaluation report found. Run an evaluation using the button above to generate metrics.
        </Alert>
      )}

      {/* ── METRICS DISPLAY ──────────────────────────────────────────────── */}
      {latestReport && !isBusy && (
        <Box>
          <Box display="flex" alignItems="center" gap={1} mb={2.5}>
            <EvalIcon color="primary" />
            <Typography variant="h5" fontWeight={700}>
              Pipeline Performance
            </Typography>
            <Chip
              label={`Last run: ${formatDate(latestReport.evaluated_at)}`}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 600, color: "primary.main", borderColor: "primary.main" }}
            />
          </Box>

          {/* 7 Stats Cards in 2 Rows Layout */}
          <Grid container spacing={2.5} mb={4}>
            {/* Row 1: Volume & Pass/Partial/Fail status */}
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="Total Queries"
                value={latestReport.total_queries}
                subtitle="Evaluated queries"
                color={theme.palette.primary.main}
                icon={<EvalIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="Passed Queries"
                value={latestReport.passed_queries}
                subtitle="Fully grounded & cited"
                color={theme.palette.success.main}
                icon={<PassedIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="Partial Matches"
                value={latestReport.partial_queries ?? 0}
                subtitle="Slightly off page number"
                color={theme.palette.warning.main}
                icon={<PassedIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="Failed Queries"
                value={latestReport.failed_queries}
                subtitle="Needs optimization"
                color={theme.palette.error.main}
                icon={<FailedIcon fontSize="small" />}
              />
            </Grid>

            {/* Row 2: RAG Pipeline Quality Ratios */}
            <Grid item xs={12} sm={4}>
              <StatCard
                label="Retrieval Accuracy"
                value={`${(latestReport.overall_retrieval_accuracy * 100).toFixed(1)}%`}
                subtitle="Page matching score"
                color="#06b6d4"
                icon={<PercentIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <StatCard
                label="Faithfulness"
                value={`${(latestReport.overall_faithfulness * 100).toFixed(1)}%`}
                subtitle="Citation alignment"
                color="#10b981"
                icon={<PercentIcon fontSize="small" />}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <StatCard
                label="Avg Response Time"
                value={`${Math.round(latestReport.avg_response_time_ms)} ms`}
                subtitle="Latency per query"
                color="#f59e0b"
                icon={<LatencyIcon fontSize="small" />}
              />
            </Grid>
          </Grid>

          {/* Visualization Section */}
          <Grid container spacing={3} mb={4}>
            <Grid item xs={12} md={6}>
              <Card sx={{ border: "1px solid", borderColor: "divider", p: 3, height: "100%" }}>
                <Typography variant="h6" fontWeight={700} mb={2.5}>
                  Evaluation Scores Summary (%)
                </Typography>
                <Box height={200}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                      <XAxis dataKey="name" fontSize={11} fontWeight={600} />
                      <YAxis domain={[0, 100]} fontSize={11} />
                      <ChartTooltip formatter={(value) => [`${value}%`, "Score"]} />
                      <Bar dataKey="score" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={40}>
                        <Cell fill="#06b6d4" />
                        <Cell fill="#10b981" />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </Card>
            </Grid>

            {/* Export & Download Card */}
            <Grid item xs={12} md={6}>
              <Card sx={{ border: "1px solid", borderColor: "divider", p: 3, height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <Box>
                  <Typography variant="h6" fontWeight={700} mb={1}>
                    Export Evaluation Report
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mb={3}>
                    Get a formal record of your RAG pipeline's quality benchmarks. The spreadsheet contains color-coded pass/fail statuses, expected cited pages, retrieved pages, and latency metrics.
                  </Typography>
                </Box>
                <Box display="flex" gap={2} flexWrap="wrap">
                  <Button
                    variant="contained"
                    startIcon={<DownloadIcon />}
                    onClick={() => window.open(evaluationService.downloadCsvUrl(), "_blank")}
                    id="golden-export-eval-csv-button"
                    sx={{
                      fontWeight: 700,
                      background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                      "&:hover": { background: "linear-gradient(135deg, #059669 0%, #047857 100%)" },
                    }}
                  >
                    Download CSV Report
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<DownloadIcon />}
                    onClick={() => window.open(evaluationService.downloadXlsxUrl(), "_blank")}
                    id="golden-export-eval-xlsx-button"
                    sx={{
                      fontWeight: 700,
                      background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                      "&:hover": { background: "linear-gradient(135deg, #d97706 0%, #b45309 100%)" },
                    }}
                  >
                    Download Excel Report
                  </Button>
                </Box>
              </Card>
            </Grid>
          </Grid>

          {/* Advanced Quality Metrics Section */}
          <Card sx={{ mb: 4, border: "1px solid", borderColor: "divider" }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={700} mb={1}>
                Advanced RAG Quality Benchmarks (Averages)
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Detailed mathematical evaluation metrics assessing chunk retrieval order, relevance density, and citation grounding quality.
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">PRECISION @ 5</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_precision_at_5 ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">RECALL @ 5</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_recall_at_5 ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">MEAN RECIPROCAL RANK (MRR)</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {(latestReport.avg_mrr ?? 0).toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">MEAN NDCG</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {(latestReport.avg_ndcg ?? 0).toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">CONTEXT PRECISION</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_context_precision ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">CONTEXT RECALL</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_context_recall ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">ANSWER RELEVANCY</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_answer_relevancy ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box p={2} sx={{ bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block">CITATION ACCURACY</Typography>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mt={0.5}>
                      {`${((latestReport.avg_citation_accuracy ?? 0) * 100).toFixed(1)}%`}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          {/* ── DETAILED RESULTS TABLE ────────────────────────────────────────── */}
          <Card sx={{ mb: 4, border: "1px solid", borderColor: "divider" }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={700} mb={2.5}>
                Evaluation Details
              </Typography>
              <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, maxHeight: 600 }}>
                <Table size="small" stickyHeader id="evaluation-details-table">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Query</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Expected Document</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Retrieved Document</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "center" }}>Expected Page</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "center" }}>Retrieved Page</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "center" }}>Retrieval Acc.</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "center" }}>Faithfulness</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "center" }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700, textAlign: "right" }}>Latency</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginatedResults.map((item, idx) => (
                      <TableRow key={idx} sx={{ "&:hover": { bgcolor: "action.hover" } }}>
                        <TableCell>
                          <Tooltip title={item.query} placement="top-start">
                            <Typography variant="body2" sx={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {item.query}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500} color="text.secondary">
                            {item.expected_document}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500} color={item.retrieved_document === item.expected_document ? "success.main" : "error.main"}>
                            {item.retrieved_document}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ textAlign: "center" }}>{item.expected_page}</TableCell>
                        <TableCell sx={{ textAlign: "center" }}>{item.retrieved_page}</TableCell>
                        <TableCell sx={{ textAlign: "center" }}>
                          <Chip
                            label={`${Math.round(item.retrieval_accuracy * 100)}%`}
                            size="small"
                            variant="outlined"
                            color={item.retrieval_accuracy >= 0.80 ? "success" : item.retrieval_accuracy > 0.0 ? "warning" : "error"}
                          />
                        </TableCell>
                        <TableCell sx={{ textAlign: "center" }}>
                          <Chip
                            label={`${Math.round(item.faithfulness * 100)}%`}
                            size="small"
                            variant="outlined"
                            color={item.faithfulness >= 0.80 ? "success" : item.faithfulness > 0.0 ? "warning" : "error"}
                          />
                        </TableCell>
                        <TableCell sx={{ textAlign: "center" }}>
                          <Chip
                            label={item.status}
                            size="small"
                            color={STATUS_COLORS[item.status] || "default"}
                          />
                        </TableCell>
                        <TableCell sx={{ textAlign: "right", fontFamily: "monospace" }}>
                          {Math.round(item.latency_ms)} ms
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              <TablePagination
                component="div"
                count={totalResults}
                page={page - 1}
                rowsPerPage={pageSize}
                rowsPerPageOptions={[10, 25, 50, 100]}
                onPageChange={(_, newPage) => setPage(newPage + 1)}
                onRowsPerPageChange={(e) => {
                  setPageSize(parseInt(e.target.value, 10));
                  setPage(1);
                }}
              />
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
};

export default EvaluationPage;
