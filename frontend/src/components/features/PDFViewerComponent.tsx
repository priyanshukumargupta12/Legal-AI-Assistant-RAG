/**
 * components/features/PDFViewerComponent.tsx
 * ==========================================
 * PDF document rendering engine using react-pdf.
 *
 * Provides:
 *   - Native PDF canvas rendering page-by-page
 *   - Page navigation (Prev, Next, Page Jump Input)
 *   - Zoom controls (Zoom In, Zoom Out, Scale Display)
 *   - Custom highlighting for citations
 */

import React, { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import {
  Box,
  IconButton,
  Typography,
  TextField,
  Paper,
  CircularProgress,
  Divider,
  useTheme,
  Alert,
  Chip,
} from "@mui/material";
import {
  ChevronLeft as PrevIcon,
  ChevronRight as NextIcon,
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  Refresh as ResetIcon,
} from "@mui/icons-material";

// Configure PDF.js worker from unpkg CDN for absolute compatibility with Vite & Vercel
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerComponentProps {
  fileUrl: string;       // Static URL, e.g. /dataset/Acts/Title11.pdf
  initialPage?: number;  // Jump to this page initially
  highlightPage?: number; // Highlight page
}

const PDFViewerComponent: React.FC<PDFViewerComponentProps> = ({
  fileUrl,
  initialPage = 1,
  highlightPage,
}) => {
  const theme = useTheme();
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState<number>(initialPage);
  const [scale, setScale] = useState<number>(1.0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Jump to initialPage when it changes (e.g. user clicked a different citation)
  useEffect(() => {
    if (initialPage) {
      setPageNumber(initialPage);
    }
  }, [initialPage, fileUrl]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setErrorMsg(null);
    if (initialPage > numPages) {
      setPageNumber(1);
    } else {
      setPageNumber(initialPage);
    }
  };

  const onDocumentLoadError = (err: Error) => {
    console.error("PDF loading error:", err);
    setErrorMsg(`Failed to load PDF document: ${err.message}. Make sure the PDF file exists in public/dataset folder.`);
  };

  const changePage = (offset: number) => {
    setPageNumber((prevPageNumber) => {
      const newPage = prevPageNumber + offset;
      return numPages ? Math.min(Math.max(1, newPage), numPages) : 1;
    });
  };

  const handlePageInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val) && numPages) {
      const page = Math.min(Math.max(1, val), numPages);
      setPageNumber(page);
    }
  };

  const handleZoom = (factor: number) => {
    setScale((prevScale) => Math.min(Math.max(0.5, prevScale + factor), 3.0));
  };

  const isHighlighted = highlightPage === pageNumber;

  return (
    <Box display="flex" flexDirection="column" alignItems="center" gap={2} width="100%">
      {/* Control bar */}
      <Paper
        elevation={2}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          maxWidth: 900,
          p: 1,
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
        }}
      >
        {/* Page Nav */}
        <Box display="flex" alignItems="center" gap={1}>
          <IconButton onClick={() => changePage(-1)} disabled={pageNumber <= 1} size="small">
            <PrevIcon />
          </IconButton>
          <Box display="flex" alignItems="center" gap={0.5}>
            <TextField
              value={pageNumber}
              onChange={handlePageInput}
              size="small"
              variant="outlined"
              sx={{
                width: 60,
                "& .MuiInputBase-input": {
                  textAlign: "center",
                  py: 0.5,
                  px: 1,
                  fontSize: "0.9rem",
                  fontWeight: 600,
                },
              }}
            />
            <Typography variant="body2" color="text.secondary">
              / {numPages ?? "..."}
            </Typography>
          </Box>
          <IconButton onClick={() => changePage(1)} disabled={numPages ? pageNumber >= numPages : true} size="small">
            <NextIcon />
          </IconButton>
        </Box>

        {/* Highlights display */}
        {isHighlighted && (
          <Chip
            label="Cited Page Highlighted"
            color="secondary"
            size="small"
            sx={{ fontWeight: 600, animation: "pulse 2s infinite" }}
          />
        )}

        {/* Zoom Controls */}
        <Box display="flex" alignItems="center" gap={1}>
          <IconButton onClick={() => handleZoom(-0.25)} disabled={scale <= 0.5} size="small">
            <ZoomOutIcon />
          </IconButton>
          <Typography variant="caption" sx={{ minWidth: 40, textAlign: "center", fontWeight: 700 }}>
            {Math.round(scale * 100)}%
          </Typography>
          <IconButton onClick={() => handleZoom(0.25)} disabled={scale >= 3.0} size="small">
            <ZoomInIcon />
          </IconButton>
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
          <IconButton onClick={() => setScale(1.0)} size="small">
            <ResetIcon />
          </IconButton>
        </Box>
      </Paper>

      {/* Main rendering canvas area */}
      {errorMsg ? (
        <Alert severity="error" sx={{ width: "100%", maxWidth: 900 }}>
          {errorMsg}
        </Alert>
      ) : (
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: theme.palette.mode === "light" ? "#F1F5F9" : "background.default",
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 3,
            overflow: "auto",
            display: "flex",
            justifyContent: "center",
            width: "100%",
            maxWidth: 900,
            maxHeight: "75vh",
            position: "relative",
            boxShadow: "inset 0px 2px 8px rgba(0,0,0,0.15)",
          }}
        >
          {/* Highlight Indicator Frame */}
          {isHighlighted && (
            <Box
              sx={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                border: "4px solid",
                borderColor: "secondary.main",
                borderRadius: 3,
                pointerEvents: "none",
                zIndex: 10,
                boxShadow: `inset 0 0 20px ${theme.palette.secondary.main}`,
              }}
            />
          )}

          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <Box display="flex" flexDirection="column" alignItems="center" py={10} gap={2}>
                <CircularProgress color="primary" />
                <Typography variant="body2" color="text.secondary">
                  Parsing PDF layers...
                </Typography>
              </Box>
            }
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderAnnotationLayer={false}
              renderTextLayer={true}
              loading={<CircularProgress sx={{ m: 5 }} />}
            />
          </Document>
        </Paper>
      )}

      {/* Styled pulse animation CSS */}
      <style>{`
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
          70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); }
          100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
        }
      `}</style>
    </Box>
  );
};

export default PDFViewerComponent;
