/**
 * pages/QueryPage.tsx
 * ===================
 * Legal AI Assistant Hybrid RAG Chat Interface.
 *
 * Displays:
 *   - Chat log with user questions and assistant answers
 *   - Citations (document, page, category) linking to the Document Viewer
 *   - Response summaries & confidence scores
 *   - Copy answer & clear chat actions
 *   - Predefined suggested questions
 *   - Interactive skeleton loaders during generation
 */

import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  TextField,
  IconButton,
  Button,
  Card,
  CardContent,
  Chip,
  Paper,
  CircularProgress,
  Grid,
  useTheme,
  Skeleton,
} from "@mui/material";
import {
  Send as SendIcon,
  ContentCopy as CopyIcon,
  DeleteOutline as ClearIcon,
  LocalActivity as CitationIcon,
  HelpOutline as SuggestIcon,
  SmartToy as RobotIcon,
  Person as UserIcon,
} from "@mui/icons-material";
import { useMutation } from "@tanstack/react-query";
import { queryService, QueryResponsePayload } from "../services/queryService";
import { useSnackbar } from "notistack";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: Date;
  summary?: string;
  confidenceScore?: number;
  citations?: Array<{
    document: string;
    page: number;
    category: string;
    snippet?: string;
  }>;
  retrievedChunks?: Array<{
    chunk_id: string;
    document: string;
    page: number;
    category: string;
    text: string;
    hybrid_score: number;
  }>;
}

const QueryPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const stored = localStorage.getItem("rag_chat_messages");
      if (stored) {
        // Parse and restore dates correctly
        return JSON.parse(stored).map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        }));
      }
    } catch (e) {
      console.error("Failed to load chat from localStorage", e);
    }
    return [];
  });
  const [inputVal, setInputVal] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Sync messages to localStorage on state changes
  useEffect(() => {
    try {
      localStorage.setItem("rag_chat_messages", JSON.stringify(messages));
    } catch (e) {
      console.error("Failed to save chat to localStorage", e);
    }
  }, [messages]);

  // Suggestions for quick legal questions
  const suggestedQuestions = [
    "What is the tax rate for qualified business income under Section 199A?",
    "What are the rules for filing a joint return for foreign nationals?",
    "Can a non-profit organization engage in lobbying activities?",
    "Explain the court judgment requirements for tax-deductible settlements.",
  ];

  // Scroll to bottom whenever messages list grows
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Mutation: submit query to backend
  const queryMutation = useMutation({
    mutationFn: (question: string) => queryService.submitQuery({ question }),
    onSuccess: (data: QueryResponsePayload) => {
      // Add assistant response to messages log
      const newResponse: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: data.answer,
        summary: data.summary,
        confidenceScore: data.confidence_score,
        citations: data.citations,
        retrievedChunks: data.retrieved_chunks,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, newResponse]);
    },
    onError: (err: any) => {
      // Add fallback error bubble
      const errorMsg: ChatMessage = {
        id: `assistant-error-${Date.now()}`,
        sender: "assistant",
        text: `Error: Unable to fetch answer from Gemini. ${err.message || ""}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    },
  });

  const handleSend = (text: string) => {
    if (!text.trim()) return;

    // Add user message
    const newUserMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setInputVal("");

    // Trigger mutation
    queryMutation.mutate(text);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    enqueueSnackbar("Answer copied to clipboard!", { variant: "info", autoHideDuration: 2000 });
  };

  const handleClear = () => {
    setMessages([]);
    try {
      localStorage.removeItem("rag_chat_messages");
    } catch (e) {
      console.error("Failed to clear chat storage", e);
    }
    enqueueSnackbar("Chat history cleared.", { variant: "default", autoHideDuration: 2000 });
  };

  const handleCitationClick = (documentName: string, category: string, page: number) => {
    navigate(`/viewer?document=${encodeURIComponent(documentName)}&category=${encodeURIComponent(category)}&page=${page}`);
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.85) return "success";
    if (score >= 0.7) return "warning";
    return "error";
  };

  return (
    <Box display="flex" flexDirection="column" sx={{ height: "calc(100vh - 110px)", width: "100%" }}>
      {/* Top action header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5} pb={1} borderBottom={`1px solid ${theme.palette.divider}`}>
        <Typography variant="body2" color="text.secondary">
          Ask complex tax queries grounded on 100 federal tax manuals and acts.
        </Typography>
        {messages.length > 0 && (
          <Button
            startIcon={<ClearIcon />}
            color="error"
            size="small"
            onClick={handleClear}
            variant="text"
            sx={{ fontWeight: 600 }}
          >
            Clear Chat
          </Button>
        )}
      </Box>

      {/* Chat scroll area */}
      <Box
        flexGrow={1}
        sx={{
          overflowY: "auto",
          mb: 2,
          p: 2,
          bgcolor: theme.palette.mode === "light" ? "#F8FAFC" : "rgba(15, 23, 42, 0.5)",
          borderRadius: 3,
          border: `1px solid ${theme.palette.divider}`,
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        {messages.length === 0 ? (
          <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" height="100%" py={5} textAlign="center" gap={3}>
            <Box
              sx={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                bgcolor: "primary.main",
                color: "primary.contrastText",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: 3,
              }}
            >
              <RobotIcon sx={{ fontSize: 32 }} />
            </Box>
            <Box>
              <Typography variant="h5" fontWeight={700}>
                US Tax & Legal AI Assistant
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400, mt: 0.5 }}>
                Type your question below or pick a suggested topic to query the hybrid Qdrant/ES indices.
              </Typography>
            </Box>

            {/* Suggestions layout */}
            <Grid container spacing={1.5} sx={{ maxWidth: 650, mt: 2 }}>
              {suggestedQuestions.map((q, idx) => (
                <Grid item xs={12} sm={6} key={idx}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      cursor: "pointer",
                      textAlign: "left",
                      height: "100%",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 1,
                      transition: "transform 0.15s, border-color 0.15s",
                      "&:hover": {
                        borderColor: "primary.main",
                        transform: "translateY(-2px)",
                        bgcolor: "action.hover",
                      },
                    }}
                    onClick={() => handleSend(q)}
                  >
                    <SuggestIcon fontSize="small" color="primary" sx={{ mt: 0.25 }} />
                    <Typography variant="body2" fontWeight={500} sx={{ fontSize: "0.85rem", lineHeight: 1.4 }}>
                      {q}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </Box>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender === "user";
            return (
              <Box
                key={msg.id}
                display="flex"
                flexDirection="column"
                alignItems={isUser ? "flex-end" : "flex-start"}
                width="100%"
              >
                {/* Bubble card */}
                <Box display="flex" gap={1.5} maxWidth="85%" flexDirection={isUser ? "row-reverse" : "row"}>
                  {/* Sender icon */}
                  <Box
                    sx={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      bgcolor: isUser ? "secondary.main" : "primary.main",
                      color: isUser ? "secondary.contrastText" : "primary.contrastText",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {isUser ? <UserIcon fontSize="small" /> : <RobotIcon fontSize="small" />}
                  </Box>

                  <Box>
                    <Paper
                      elevation={1}
                      sx={{
                        p: 2,
                        borderRadius: 3,
                        borderTopLeftRadius: isUser ? 3 : 0,
                        borderTopRightRadius: isUser ? 0 : 3,
                        bgcolor: isUser ? "secondary.main" : "background.paper",
                        color: isUser ? "secondary.contrastText" : "text.primary",
                        border: isUser ? "none" : `1px solid ${theme.palette.divider}`,
                      }}
                    >
                      <Typography variant="body1" sx={{ whiteSpace: "pre-line", wordBreak: "break-word" }}>
                        {msg.text}
                      </Typography>
                    </Paper>

                    {/* Meta info & Citations for Assistant response */}
                    {!isUser && msg.summary && (
                      <Box mt={1.5} display="flex" flexDirection="column" gap={1.5}>
                        {/* Summary & Metrics bar */}
                        <Box display="flex" gap={1} alignItems="center" flexWrap="wrap">
                          <Chip
                            label={`Confidence: ${Math.round((msg.confidenceScore ?? 0.85) * 100)}%`}
                            color={getConfidenceColor(msg.confidenceScore ?? 0.85)}
                            size="small"
                            sx={{ fontWeight: 700 }}
                          />
                          <IconButton size="small" onClick={() => handleCopy(msg.text)}>
                            <CopyIcon fontSize="small" />
                          </IconButton>
                        </Box>

                        {/* Collapsible/neat Summary Card */}
                        <Card variant="outlined" sx={{ borderRadius: 2 }}>
                          <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" gutterBottom>
                              EXECUTIVE SUMMARY:
                            </Typography>
                            <Typography variant="body2" sx={{ fontStyle: "italic", fontSize: "0.85rem" }}>
                              {msg.summary}
                            </Typography>
                          </CardContent>
                        </Card>

                        {/* Citations cards layout */}
                        {msg.citations && msg.citations.length > 0 && (
                          <Box>
                            <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 0.75 }}>
                              SOURCE CITATIONS (CLICK TO VIEW PDF):
                            </Typography>
                            <Grid container spacing={1.5}>
                              {msg.citations.map((cite, idx) => (
                                <Grid item xs={12} sm={6} key={idx}>
                                  <Card
                                    variant="outlined"
                                    onClick={() => handleCitationClick(cite.document, cite.category, cite.page)}
                                    sx={{
                                      borderRadius: 2,
                                      cursor: "pointer",
                                      transition: "border-color 0.2s, transform 0.2s",
                                      "&:hover": {
                                        borderColor: "secondary.main",
                                        transform: "translateY(-1px)",
                                        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                                      },
                                    }}
                                  >
                                    <CardContent sx={{ p: 1.2, "&:last-child": { pb: 1.2 } }}>
                                      <Box display="flex" gap={1} alignItems="center" mb={cite.snippet ? 1 : 0}>
                                        <CitationIcon color="secondary" fontSize="small" />
                                        <Box sx={{ minWidth: 0 }}>
                                          <Typography variant="subtitle2" noWrap sx={{ fontSize: "0.8rem", fontWeight: 700 }}>
                                            {cite.document}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary" display="block">
                                            Page {cite.page} • {cite.category}
                                          </Typography>
                                        </Box>
                                      </Box>
                                      {cite.snippet && (
                                        <Typography 
                                          variant="body2" 
                                          color="text.secondary" 
                                          sx={{ 
                                            fontSize: "0.75rem", 
                                            fontStyle: "italic", 
                                            bgcolor: theme.palette.mode === "light" ? "#F1F5F9" : "#1E293B",
                                            p: 1, 
                                            borderRadius: 1.5,
                                            mt: 1,
                                            borderLeft: `3px solid ${theme.palette.secondary.main}`,
                                            whiteSpace: "pre-line",
                                            lineHeight: 1.3
                                          }}
                                        >
                                          "{cite.snippet.length > 180 ? cite.snippet.substring(0, 180) + '...' : cite.snippet}"
                                        </Typography>
                                      )}
                                    </CardContent>
                                  </Card>
                                </Grid>
                              ))}
                            </Grid>
                          </Box>
                        )}

                        {/* Retrieved Chunks layout (Transparency list) */}
                        {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                          <Box>
                            <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 0.75 }}>
                              TRANSPARENT RETRIEVAL CONTEXT (TOP-K CHUNKS):
                            </Typography>
                            <Box display="flex" flexDirection="column" gap={1}>
                              {msg.retrievedChunks.map((chunk, idx) => (
                                <Paper 
                                  variant="outlined" 
                                  key={idx} 
                                  sx={{ 
                                    p: 1.5, 
                                    borderRadius: 2, 
                                    bgcolor: theme.palette.mode === "light" ? "#F8FAFC" : "rgba(30, 41, 59, 0.3)" 
                                  }}
                                >
                                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.75}>
                                    <Typography variant="caption" fontWeight={700} color="primary.main">
                                      Chunk #{idx + 1} | {chunk.document} | Page {chunk.page}
                                    </Typography>
                                    <Chip 
                                      label={`Score: ${chunk.hybrid_score.toFixed(4)}`} 
                                      size="small" 
                                      variant="outlined"
                                      sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700 }}
                                    />
                                  </Box>
                                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.75rem", lineHeight: 1.4 }}>
                                    {chunk.text}
                                  </Typography>
                                </Paper>
                              ))}
                            </Box>
                          </Box>
                        )}
                      </Box>
                    )}
                  </Box>
                </Box>
              </Box>
            );
          })
        )}

        {/* Loader skeleton during API call */}
        {queryMutation.isPending && (
          <Box display="flex" gap={1.5} width="85%">
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                bgcolor: "primary.main",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CircularProgress size={18} color="inherit" />
            </Box>
            <Box flexGrow={1} display="flex" flexDirection="column" gap={1.5}>
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, borderTopLeftRadius: 0, width: "100%" }}>
                <Skeleton width="100%" height={20} />
                <Skeleton width="90%" height={20} />
                <Skeleton width="60%" height={20} />
              </Paper>
            </Box>
          </Box>
        )}
        <div ref={chatEndRef} />
      </Box>

      {/* Input bar */}
      <Box component="form" onSubmit={(e) => { e.preventDefault(); handleSend(inputVal); }} display="flex" gap={1.5} alignItems="center">
        <TextField
          placeholder="Ask a legal tax question (e.g. Qualified business deduction QBI rules)..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          variant="outlined"
          fullWidth
          size="medium"
          disabled={queryMutation.isPending}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 3,
            },
          }}
        />
        <IconButton
          color="primary"
          type="submit"
          disabled={!inputVal.trim() || queryMutation.isPending}
          sx={{
            p: 1.5,
            bgcolor: "primary.main",
            color: "primary.contrastText",
            "&:hover": {
              bgcolor: "primary.dark",
            },
            "&.Mui-disabled": {
              bgcolor: "action.disabledBackground",
              color: "action.disabled",
            },
          }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
};

export default QueryPage;
