/**
 * pages/ViewerPage.tsx
 * ====================
 * Document Viewer Page.
 *
 * Wraps PDFViewerComponent and loads the PDF file dynamically based on
 * URL search parameters (?document=Title11.pdf&category=Acts&page=5).
 * Also integrates the POST /summarize API to generate and display document-level summaries.
 */

import React from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  Divider,
  CircularProgress,
  Paper,
  Chip,
} from "@mui/material";
import {
  ArrowBack as BackIcon,
  AutoAwesome as SummarizeIcon,
  Description as DocIcon,
} from "@mui/icons-material";
import { useMutation } from "@tanstack/react-query";
import { documentService } from "../services/documentService";
import PDFViewerComponent from "../components/features/PDFViewerComponent";
import { DOCUMENTS_REGISTRY } from "../assets/documentsRegistry";

const ViewerPage: React.FC = () => {
  const [searchParams] = useSearchParams();

  const docName = searchParams.get("document");
  const category = searchParams.get("category");
  const pageParam = searchParams.get("page");
  const initialPage = pageParam ? parseInt(pageParam, 10) : 1;

  // Find document metadata in static registry
  const docMeta = DOCUMENTS_REGISTRY.find(
    (d) => d.file_name === docName && d.category === category
  );

  // Mutation: Generate document summary
  const summaryMutation = useMutation({
    mutationFn: () => {
      if (!docMeta) throw new Error("Document metadata not found.");
      return documentService.summarizeDocument(docMeta.document_id);
    },
  });

  if (!docName || !category) {
    return (
      <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={12} gap={2}>
        <DocIcon sx={{ fontSize: 60, color: "text.disabled" }} />
        <Typography variant="h6" fontWeight={700}>
          No Document Selected
        </Typography>
        <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ maxWidth: 300, mb: 2 }}>
          Please go to the Document Registry page and click Open on any legal document to view it.
        </Typography>
        <Button component={Link} to="/dataset" variant="contained" startIcon={<BackIcon />}>
          View Registry
        </Button>
      </Box>
    );
  }

  // Construct PDF URL from backend API (PDFs live on the Render server, not Vercel static files)
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
  const fileUrl = `${apiBase}/dataset/pdf?category=${encodeURIComponent(category)}&document=${encodeURIComponent(docName)}`;

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    return (bytes / (k * k)).toFixed(2) + " MB";
  };

  return (
    <Box>
      {/* Navigation and Metadata header */}
      <Box mb={3} display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
        <Box>
          <Button
            component={Link}
            to="/dataset"
            startIcon={<BackIcon />}
            size="small"
            variant="text"
            sx={{ fontWeight: 600, mb: 1 }}
          >
            Back to Registry
          </Button>
          <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.03em" }}>
            {docName}
          </Typography>
          <Box display="flex" gap={1.5} alignItems="center" mt={1} flexWrap="wrap">
            <Chip label={category} size="small" />
            {docMeta && (
              <>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  Total Pages: {docMeta.page_count}
                </Typography>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  File Size: {formatBytes(docMeta.file_size_bytes)}
                </Typography>
              </>
            )}
          </Box>
        </Box>

        {/* Summarize triggering button */}
        {docMeta && (
          <Button
            variant="outlined"
            color="secondary"
            startIcon={<SummarizeIcon />}
            onClick={() => summaryMutation.mutate()}
            disabled={summaryMutation.isPending}
          >
            {summaryMutation.isPending ? "Summarizing..." : "Summarize Document"}
          </Button>
        )}
      </Box>

      <Grid container spacing={3}>
        {/* PDF viewer canvas */}
        <Grid item xs={12} md={summaryMutation.data || summaryMutation.isPending ? 8 : 12}>
          <Paper elevation={1} sx={{ p: 2, borderRadius: 3, display: "flex", justifyContent: "center" }}>
            <PDFViewerComponent
              fileUrl={fileUrl}
              initialPage={initialPage}
              highlightPage={initialPage}
            />
          </Paper>
        </Grid>

        {/* Collapsible summary sidebar */}
        {(summaryMutation.data || summaryMutation.isPending) && (
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%", maxHeight: "80vh", overflowY: "auto", borderRadius: 3 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" fontWeight={700} display="flex" alignItems="center" gap={1} mb={1}>
                  <SummarizeIcon color="secondary" /> AI Legal Summary
                </Typography>
                <Divider sx={{ mb: 2 }} />

                {summaryMutation.isPending ? (
                  <Box display="flex" flexDirection="column" alignItems="center" py={10} gap={2}>
                    <CircularProgress color="secondary" />
                    <Typography variant="body2" color="text.secondary">
                      Generating document executive summary with Gemini...
                    </Typography>
                  </Box>
                ) : (
                  <Box>
                    <Typography
                      variant="body2"
                      color="text.primary"
                      sx={{
                        lineHeight: 1.7,
                        fontSize: "0.9rem",
                        whiteSpace: "pre-line",
                        fontStyle: "italic",
                      }}
                    >
                      {summaryMutation.data?.summary}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default ViewerPage;
