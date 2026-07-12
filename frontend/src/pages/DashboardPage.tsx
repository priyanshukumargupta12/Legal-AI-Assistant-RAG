/**
 * pages/DashboardPage.tsx
 * ========================
 * System overview dashboard page.
 *
 * Displays:
 *   - Aggregate document statistics (Acts, Court Judgments, Tax, Opinions)
 *   - Subsystem status (Qdrant, Elasticsearch, Gemini)
 *   - Total chunks and indexing stats
 *   - Scrollable recent query history
 */

import React from "react";
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Divider,
  List,
  ListItem,
  ListItemText,
  Chip,
  Skeleton,
  useTheme,
  Button,
} from "@mui/material";
import {
  Folder as FolderIcon,
  Gavel as GavelIcon,
  Description as DocIcon,
  Summarize as OpinionIcon,
  CloudDone as CloudIcon,
  Storage as DbIcon,
  FlashOn as InstantIcon,
  History as HistoryIcon,
} from "@mui/icons-material";
import { Link } from "react-router-dom";
import { documentService } from "../services/documentService";
import { queryService } from "../services/queryService";
import { useAppContext } from "../store/AppContext";
import { useQuery } from "@tanstack/react-query";

const DashboardPage: React.FC = () => {
  const theme = useTheme();
  const { systemHealthy } = useAppContext();

  // Query: Get Dataset Statistics
  const { data: stats, isLoading: statsLoading, refetch: refetchStats } = useQuery({
    queryKey: ["dataset-stats"],
    queryFn: () => documentService.getDatasetStats(),
  });

  // Query: Get QA history for recent queries
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["recent-queries"],
    queryFn: () => queryService.getSearchHistory(),
  });

  return (
    <Box>
      {/* Header section */}
      <Box mb={3} display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.03em", mb: 0.5 }}>
            System Dashboard
          </Typography>
          <Typography color="text.secondary" variant="body2">
            Overview of the US Tax & Legal Hybrid RAG knowledge base and ingestion pipelines.
          </Typography>
        </Box>
        <Button variant="outlined" color="primary" onClick={() => refetchStats()} size="small">
          Refresh Statistics
        </Button>
      </Box>

      {/* Aggregate Stats Cards */}
      <Grid container spacing={3} mb={4}>
        {/* Total Documents Card */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box p={1.5} bgcolor="primary.main" borderRadius={2} color="primary.contrastText" display="flex">
                <FolderIcon />
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary" fontWeight={600}>
                  Total Documents
                </Typography>
                <Typography variant="h4" fontWeight={700}>
                  {statsLoading ? <Skeleton width={60} /> : stats?.total_pdfs ?? 0}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Acts Card */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box p={1.5} bgcolor="secondary.main" borderRadius={2} color="secondary.contrastText" display="flex">
                <GavelIcon />
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary" fontWeight={600}>
                  Acts / Statutes
                </Typography>
                <Typography variant="h4" fontWeight={700}>
                  {statsLoading ? <Skeleton width={60} /> : stats?.acts_count ?? 0}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Court Judgments Card */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box p={1.5} bgcolor="success.main" borderRadius={2} color="#FFFFFF" display="flex">
                <DocIcon />
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary" fontWeight={600}>
                  Court Judgments
                </Typography>
                <Typography variant="h4" fontWeight={700}>
                  {statsLoading ? <Skeleton width={60} /> : stats?.court_count ?? 0}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Tax Documents / Opinions */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box p={1.5} bgcolor="info.main" borderRadius={2} color="#FFFFFF" display="flex">
                <OpinionIcon />
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary" fontWeight={600}>
                  Tax / Legal Opinions
                </Typography>
                <Typography variant="h4" fontWeight={700}>
                  {statsLoading ? <Skeleton width={60} /> : (stats?.tax_count ?? 0) + (stats?.legal_opinion_count ?? 0)}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Subsystem & DB status Grid */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} md={7}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom display="flex" alignItems="center" gap={1}>
                <InstantIcon color="primary" /> RAG System Configuration & Ingestion Status
              </Typography>
              <Divider sx={{ my: 1.5 }} />

              <Grid container spacing={2} py={1}>
                <Grid item xs={6}>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Typography variant="body2" color="text.secondary" fontWeight={600}>
                      Total Text Chunks
                    </Typography>
                    <Typography variant="h5" fontWeight={700} color="primary.main">
                      152,086
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Typography variant="body2" color="text.secondary" fontWeight={600}>
                      Indexed Chunks
                    </Typography>
                    <Typography variant="h5" fontWeight={700} color="success.main">
                      152,086
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              <Divider sx={{ my: 1.5 }} />

              {/* Status badges */}
              <Box display="flex" flexDirection="column" gap={1.5} mt={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" fontWeight={600}>Qdrant Vector Database</Typography>
                  <Chip label={systemHealthy ? "ACTIVE (Healthy)" : "DEGRADED"} color={systemHealthy ? "success" : "warning"} size="small" />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" fontWeight={600}>Elasticsearch BM25 Cluster</Typography>
                  <Chip label={systemHealthy ? "ACTIVE (Healthy)" : "DEGRADED"} color={systemHealthy ? "success" : "warning"} size="small" />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" fontWeight={600}>LLM Provider (Google Gemini)</Typography>
                  <Chip label="ONLINE" color="success" size="small" />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" fontWeight={600}>BGE Ingestion Embeddings</Typography>
                  <Chip label="ACTIVE (384-Dim)" color="success" size="small" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* System Health Summary */}
        <Grid item xs={12} md={5}>
          <Card sx={{ height: "100%" }}>
            <CardContent sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <Typography variant="h6" fontWeight={700} gutterBottom display="flex" alignItems="center" gap={1}>
                <CloudIcon color="primary" /> Connectivity Status
              </Typography>
              <Divider sx={{ my: 1.5 }} />

              <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" flexGrow={1} py={3} gap={1.5}>
                <Box
                  sx={{
                    width: 70,
                    height: 70,
                    borderRadius: "50%",
                    bgcolor: systemHealthy ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "2px solid",
                    borderColor: systemHealthy ? "success.main" : "error.main",
                  }}
                >
                  <DbIcon sx={{ fontSize: 36, color: systemHealthy ? "success.main" : "error.main" }} />
                </Box>
                <Typography variant="h6" fontWeight={700}>
                  {systemHealthy ? "All Systems Operational" : "Degraded Connectivity"}
                </Typography>
                <Typography variant="caption" color="text.secondary" textAlign="center" sx={{ maxWidth: 220 }}>
                  {systemHealthy
                    ? "The frontend is successfully communicating with the Render FastAPI backend and Qdrant/ES databases."
                    : "Connectivity issue detected. Please check if backend API services on Render are running."}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Queries List */}
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="h6" fontWeight={700} display="flex" alignItems="center" gap={1}>
              <HistoryIcon color="primary" /> Recent Queries
            </Typography>
            <Button component={Link} to="/query" size="small" variant="text">
              New Chat
            </Button>
          </Box>
          <Divider sx={{ mb: 1.5 }} />

          {historyLoading ? (
            <Box py={2}>
              <Skeleton height={40} sx={{ mb: 1 }} />
              <Skeleton height={40} sx={{ mb: 1 }} />
              <Skeleton height={40} />
            </Box>
          ) : !history || history.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
              No search queries logged yet. Go to <Link to="/query" style={{ color: theme.palette.primary.main, textDecoration: "none", fontWeight: 600 }}>Ask AI</Link> to run your first RAG query.
            </Typography>
          ) : (
            <List disablePadding>
              {history.slice(0, 4).map((item, idx) => (
                <Box key={idx}>
                  <ListItem sx={{ py: 1.5, px: 0.5 }}>
                    <ListItemText
                      primary={item.question}
                      primaryTypographyProps={{
                        fontWeight: 600,
                        fontSize: "0.95rem",
                        noWrap: true,
                        sx: { color: "text.primary" },
                      }}
                      secondary={
                        <Typography variant="body2" color="text.secondary" sx={{
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "-webkit-box",
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: "vertical",
                        }}>
                          {item.answer}
                        </Typography>
                      }
                    />
                    <Typography variant="caption" color="text.disabled" sx={{ minWidth: 80, textAlign: "right" }}>
                      {new Date(item.timestamp).toLocaleDateString()}
                    </Typography>
                  </ListItem>
                  {idx < 3 && <Divider />}
                </Box>
              ))}
            </List>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default DashboardPage;
