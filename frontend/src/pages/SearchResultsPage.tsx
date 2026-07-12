/**
 * pages/SearchResultsPage.tsx
 * ===========================
 * RAG Hybrid Search Explorer.
 *
 * Provides a dedicated interface to search the Qdrant & Elasticsearch indices.
 * Displays:
 *   - Search stats (Candidate pools, Latency)
 *   - Fused text chunks from the Weighted Rank Fusion engine
 *   - Score breakdowns: Vector score, BM25 score, Fused Hybrid score
 *   - Navigation buttons opening the document viewer at the exact cited page
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  Paper,
  Divider,
  useTheme,
  Skeleton,
  FormControl,
  Select,
  MenuItem,
} from "@mui/material";
import {
  Search as SearchIcon,
  Visibility as OpenIcon,
  Speed as LatencyIcon,
  Hub as FusionIcon,
} from "@mui/icons-material";
import { useMutation } from "@tanstack/react-query";
import { queryService } from "../services/queryService";

const SearchResultsPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");

  const categories = ["All", "Acts", "CourtJudgement", "Tax", "Legal_opinion"];
  const categoryLabels: Record<string, string> = {
    All: "All Categories",
    Acts: "Acts & Statutes",
    CourtJudgement: "Court Judgments",
    Tax: "Tax Documents",
    Legal_opinion: "Legal Opinions",
  };

  // Mutation: query hybrid search API
  const searchMutation = useMutation({
    mutationFn: () => queryService.submitSearch(query, category),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      searchMutation.mutate();
    }
  };

  const handleOpenDocument = (documentName: string, categoryName: string, page: number) => {
    navigate(`/viewer?document=${encodeURIComponent(documentName)}&category=${encodeURIComponent(categoryName)}&page=${page}`);
  };

  const results = searchMutation.data?.results ?? [];
  const searchStats = searchMutation.data;

  return (
    <Box>
      {/* Title */}
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.03em", mb: 0.5 }}>
          RAG Retrieval Explorer
        </Typography>
        <Typography color="text.secondary" variant="body2">
          Query dense semantic vectors and keyword indices in parallel. Visualize scores and fusion rankings.
        </Typography>
      </Box>

      {/* Search Input Bar */}
      <Paper component="form" onSubmit={handleSearchSubmit} sx={{ p: 2, mb: 4, borderRadius: 2 }} elevation={1}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={7} md={8}>
            <TextField
              placeholder="Search legal concepts (e.g., Section 199A pass-through deduction limits)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              fullWidth
              size="medium"
              InputProps={{
                startAdornment: <SearchIcon color="action" sx={{ mr: 1 }} />,
              }}
            />
          </Grid>
          <Grid item xs={12} sm={3} md={2}>
            <FormControl fullWidth>
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                size="medium"
                sx={{ borderRadius: 2 }}
              >
                {categories.map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {categoryLabels[cat]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2} md={2}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              size="large"
              disabled={!query.trim() || searchMutation.isPending}
              sx={{ height: 48, borderRadius: 2 }}
            >
              Retrieve
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Loading state skeletons */}
      {searchMutation.isPending && (
        <Box display="flex" flexDirection="column" gap={3}>
          <Skeleton height={50} width={250} />
          <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 3 }} />
          <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 3 }} />
          <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 3 }} />
        </Box>
      )}

      {/* Inactive state */}
      {!searchMutation.isPending && !searchStats && (
        <Typography variant="body2" color="text.secondary" textAlign="center" py={10}>
          Enter a search query and click Retrieve to fetch and inspect RAG source chunks.
        </Typography>
      )}

      {/* Results view */}
      {searchStats && !searchMutation.isPending && (
        <Box>
          {/* Retrieval Stats Panel */}
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 3,
              borderRadius: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 2,
            }}
          >
            <Box display="flex" alignItems="center" gap={1}>
              <FusionIcon color="primary" />
              <Typography variant="subtitle2" fontWeight={700}>
                Rank Fusion Summary
              </Typography>
            </Box>
            <Box display="flex" gap={3}>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">Qdrant Matches</Typography>
                <Typography variant="body2" fontWeight={700}>{searchStats.vector_count} chunks</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">ES Matches</Typography>
                <Typography variant="body2" fontWeight={700}>{searchStats.bm25_count} chunks</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">Total Candidates</Typography>
                <Typography variant="body2" fontWeight={700}>{searchStats.total_candidates} candidates</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block"><LatencyIcon sx={{ fontSize: 14, verticalAlign: "middle" }} /> Latency</Typography>
                <Typography variant="body2" fontWeight={700} color="primary.main">{searchStats.retrieval_time_ms.toFixed(1)} ms</Typography>
              </Box>
            </Box>
          </Paper>

          {/* Results List */}
          <Box display="flex" flexDirection="column" gap={3}>
            {results.length === 0 ? (
              <Typography variant="body1" color="text.secondary" textAlign="center" py={6}>
                No relevant text passages retrieved. Try refining your keywords.
              </Typography>
            ) : (
              results.map((chunk, index) => (
                <Card key={chunk.chunk_id} elevation={1} sx={{ borderRadius: 3 }}>
                  <CardContent sx={{ p: 3, "&:last-child": { pb: 3 } }}>
                    {/* Header */}
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2} mb={2}>
                      <Box>
                        <Chip
                          label={`Rank #${index + 1}`}
                          color="secondary"
                          size="small"
                          sx={{ fontWeight: 700, mr: 1 }}
                        />
                        <Typography variant="subtitle1" component="span" fontWeight={700} color="text.primary">
                          {chunk.document}
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary" mt={0.5}>
                          Category: {categoryLabels[chunk.category] || chunk.category} • Page {chunk.page}
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<OpenIcon />}
                        onClick={() => handleOpenDocument(chunk.document, chunk.category, chunk.page)}
                      >
                        Open PDF
                      </Button>
                    </Box>

                    {/* Text Preview */}
                    <Typography
                      variant="body2"
                      color="text.primary"
                      sx={{
                        lineHeight: 1.7,
                        p: 2,
                        borderRadius: 2,
                        bgcolor: theme.palette.mode === "light" ? "#F8FAFC" : "rgba(15, 23, 42, 0.3)",
                        borderLeft: `3px solid ${theme.palette.primary.main}`,
                        mb: 2,
                        fontFamily: '"Outfit", "Inter", sans-serif',
                      }}
                    >
                      {chunk.text}
                    </Typography>

                    <Divider sx={{ my: 1.5 }} />

                    {/* Scores Footer */}
                    <Box display="flex" gap={3} flexWrap="wrap">
                      <Box>
                        <Typography variant="caption" color="text.secondary" display="block">Vector Cosine Similarity</Typography>
                        <Typography variant="body2" fontWeight={700} color="primary.main">{chunk.vector_score.toFixed(4)}</Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary" display="block">Elasticsearch BM25 Score</Typography>
                        <Typography variant="body2" fontWeight={700} color="secondary.main">{chunk.bm25_score.toFixed(4)}</Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary" display="block">Weighted Rank Fusion (RRF)</Typography>
                        <Chip
                          label={chunk.hybrid_score.toFixed(4)}
                          color="primary"
                          size="small"
                          sx={{ fontWeight: 700, mt: 0.5 }}
                        />
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              ))
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default SearchResultsPage;
