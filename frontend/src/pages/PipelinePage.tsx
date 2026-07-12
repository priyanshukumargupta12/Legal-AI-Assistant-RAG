/**
 * pages/PipelinePage.tsx
 * =====================
 * Pipeline Monitor Page.
 *
 * Visualises the full hybrid RAG pipeline:
 *   Dataset -> Parser -> Chunking -> Embedding -> Qdrant / ES -> Fusion -> Graph RAG -> Gemini
 *
 * Implements:
 *   - Framer Motion sequential node highlighting
 *   - Pulse animation loops showing operational status
 *   - Diagnostic details for each pipeline node
 */

import React, { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Chip,
  useTheme,
  Grid,
} from "@mui/material";
import {
  PlayArrow as StartIcon,
  CheckCircle as CompletedIcon,
  Sync as RunningIcon,
  ChevronRight as ArrowRightIcon,
  Dns as NodeIcon,
} from "@mui/icons-material";
import { motion } from "framer-motion";

interface PipelineNode {
  id: string;
  name: string;
  description: string;
  details: string[];
}

const PipelinePage: React.FC = () => {
  const theme = useTheme();
  const [simulationIndex, setSimulationIndex] = useState<number | null>(null);

  // Complete list of RAG nodes in the pipeline
  const pipelineNodes: PipelineNode[] = [
    {
      id: "dataset",
      name: "1. Dataset Registry",
      description: "100 PDF files in category subfolders.",
      details: ["Acts, Judgments, Tax Codes, Opinions", "Static local storage folder", "SHA256 checksum registry"],
    },
    {
      id: "parser",
      name: "2. PDF Parser",
      description: "Extract text page-by-page natively.",
      details: ["PyMuPDF text extraction", "Standardized Page JSON output", "Header/Footer filtration"],
    },
    {
      id: "chunker",
      name: "3. Recursive Chunker",
      description: "Generates semantic text overlapping passages.",
      details: ["Chunk size: 1020 characters", "Overlap: 100 characters", "Metadata inheritance (doc name, page)"],
    },
    {
      id: "embeddings",
      name: "4. Embedder (BGE)",
      description: "Calculates dense vector embeddings locally.",
      details: ["Model: BGE-Small-EN-v1.5", "Dimensions: 384", "Tensor processing caching"],
    },
    {
      id: "qdrant",
      name: "5. Qdrant Cloud",
      description: "Vector database for semantic search.",
      details: ["Cosine distance metric", "Payload-bound vectors", "Fast query indexing"],
    },
    {
      id: "elasticsearch",
      name: "6. Elasticsearch",
      description: "BM25 keyword inversion index.",
      details: ["Standard analyzer mapping", "Boolean search query parameters", "Term frequency scoring"],
    },
    {
      id: "fusion",
      name: "7. Hybrid Retrieval",
      description: "Reciprocal Rank Fusion fusion engine.",
      details: ["Qdrant and ES search in parallel", "Weighted fusion RRF ranking", "Top 5 fused chunks extraction"],
    },
    {
      id: "graphrag",
      name: "8. Graph RAG Enrichment",
      description: "Entity relation graph query context.",
      details: ["Node-link entity relationships", "Sub-graph semantic matching", "Fact list grounding"],
    },
    {
      id: "gemini",
      name: "9. Google Gemini",
      description: "Grounded LLM generative answer formulation.",
      details: ["Model: Gemini 1.5 Pro", "Citations mapping overlay", "Confidence score scoring"],
    },
  ];

  const triggerSimulation = () => {
    setSimulationIndex(0);
    const interval = setInterval(() => {
      setSimulationIndex((prev) => {
        if (prev !== null && prev < pipelineNodes.length - 1) {
          return prev + 1;
        }
        clearInterval(interval);
        return null; // Reset when complete
      });
    }, 1200); // 1.2s delay per stage
  };

  const getNodeStatus = (index: number) => {
    if (simulationIndex === null) return "COMPLETED"; // Static active state
    if (simulationIndex === index) return "RUNNING";
    if (simulationIndex > index) return "COMPLETED";
    return "PENDING";
  };

  const getStatusChip = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <Chip label="COMPLETED" color="success" size="small" icon={<CompletedIcon />} sx={{ fontWeight: 700 }} />;
      case "RUNNING":
        return (
          <Chip
            label="RUNNING"
            color="primary"
            size="small"
            icon={<RunningIcon className="spin" />}
            sx={{ fontWeight: 700, animation: "pulse 1.5s infinite" }}
          />
        );
      default:
        return <Chip label="PENDING" size="small" sx={{ fontWeight: 700 }} />;
    }
  };

  return (
    <Box>
      {/* Title */}
      <Box mb={4} display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.03em", mb: 0.5 }}>
            Pipeline Monitor
          </Typography>
          <Typography color="text.secondary" variant="body2">
            Inspect the live status, components, and diagnostic logs of the RAG pipeline subsystems.
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          startIcon={<StartIcon />}
          onClick={triggerSimulation}
          disabled={simulationIndex !== null}
        >
          {simulationIndex !== null ? "Simulating..." : "Simulate Pipeline Flow"}
        </Button>
      </Box>

      {/* Nodes list visual graph */}
      <Box display="flex" flexDirection="column" gap={2} mb={5}>
        {pipelineNodes.map((node, index) => {
          const status = getNodeStatus(index);
          const isActive = status === "RUNNING";
          const isCompleted = status === "COMPLETED";

          return (
            <motion.div
              key={node.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Paper
                elevation={isActive ? 3 : 1}
                sx={{
                  p: 2.5,
                  borderRadius: 3,
                  border: "1px solid",
                  borderColor: isActive
                    ? "primary.main"
                    : isCompleted
                    ? "success.light"
                    : "divider",
                  bgcolor: isActive
                    ? "rgba(59, 130, 246, 0.05)"
                    : isCompleted
                    ? "background.paper"
                    : "rgba(30, 41, 59, 0.2)",
                  transition: "all 0.3s ease",
                  boxShadow: isActive ? `0 0 15px ${theme.palette.primary.main}40` : "none",
                }}
              >
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={12} sm={3}>
                    <Box display="flex" alignItems="center" gap={1.5}>
                      <NodeIcon color={isActive ? "primary" : isCompleted ? "success" : "action"} />
                      <Typography variant="subtitle1" fontWeight={700}>
                        {node.name}
                      </Typography>
                    </Box>
                  </Grid>

                  <Grid item xs={12} sm={5}>
                    <Typography variant="body2" color="text.secondary">
                      {node.description}
                    </Typography>
                  </Grid>

                  <Grid item xs={12} sm={2}>
                    <Box sx={{ minWidth: 100 }}>{getStatusChip(status)}</Box>
                  </Grid>

                  {/* Diagnostic details dropdown */}
                  <Grid item xs={12} sm={2} alignSelf="flex-end">
                    <Box display="flex" flexDirection="column" gap={0.5}>
                      {node.details.slice(0, 2).map((det, idx) => (
                        <Typography key={idx} variant="caption" color="text.disabled" display="block">
                          • {det}
                        </Typography>
                      ))}
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
              {index < pipelineNodes.length - 1 && (
                <Box display="flex" justifyContent="center" py={0.5} color="text.disabled">
                  <ArrowRightIcon sx={{ transform: "rotate(90deg)", fontSize: 28 }} />
                </Box>
              )}
            </motion.div>
          );
        })}
      </Box>

      {/* Styled rotations & pulse animation CSS */}
      <style>{`
        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.05); }
          100% { transform: scale(1); }
        }
        .spin {
          animation: spin 3s linear infinite;
        }
        @keyframes spin {
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </Box>
  );
};

export default PipelinePage;
