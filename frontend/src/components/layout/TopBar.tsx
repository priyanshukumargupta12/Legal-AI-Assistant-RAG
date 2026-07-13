/**
 * components/layout/TopBar.tsx
 * ============================
 * Application header/toolbar displaying status metrics and settings.
 *
 * Shows:
 *   - Active page name
 *   - Connectivity Health Indicator (pinging backend)
 *   - Current LLM Provider selector
 *   - Light/Dark theme toggler
 */

import React from "react";
import { useLocation } from "react-router-dom";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Chip,
  FormControl,
  Select,
  MenuItem,
  Tooltip,
} from "@mui/material";
import {
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  CheckCircle as HealthyIcon,
  ErrorOutline as UnhealthyIcon,
  SmartToy as RobotIcon,
} from "@mui/icons-material";
import { useAppContext } from "../../store/AppContext";

const TopBar: React.FC = () => {
  const location = useLocation();
  const {
    systemHealthy,
    llmProvider,
    setLlmProvider,
    themeMode,
    toggleThemeMode,
  } = useAppContext();

  // Determine page title based on location
  const getPageTitle = (path: string): string => {
    switch (path) {
      case "/":
        return "System Dashboard";
      case "/dataset":
        return "Predefined Dataset Registry";
      case "/processing":
        return "Pipeline Orchestrator & Data Processing";
      case "/query":
        return "Ask Legal AI (Hybrid RAG Chat)";
      case "/search":
        return "RAG Hybrid Search Retrieval Results";
      case "/viewer":
        return "US Legal & Tax Document Viewer";
      case "/evaluation":
        return "Golden Set Evaluation Metrics";
      case "/history":
        return "QA Conversation History";
      case "/pipeline":
        return "Pipeline Infrastructure Monitor";
      default:
        return "Enterprise Legal AI Assistant";
    }
  };

  const handleProviderChange = (e: any) => {
    setLlmProvider(e.target.value);
  };

  return (
    <AppBar position="sticky" color="default" sx={{ width: "100%" }}>
      <Toolbar sx={{ justifyContent: "space-between", px: { xs: 2, sm: 3 } }}>
        {/* Page Title */}
        <Typography variant="h5" fontWeight={700} sx={{ letterSpacing: "-0.02em" }}>
          {getPageTitle(location.pathname)}
        </Typography>

        {/* Action Controls & Health */}
        <Box display="flex" alignItems="center" gap={2}>
          {/* Health check status indicator */}
          <Tooltip title={systemHealthy ? "Backend server connection active" : "Backend server disconnected"}>
            <Chip
              icon={systemHealthy ? <HealthyIcon color="success" /> : <UnhealthyIcon color="error" />}
              label={systemHealthy ? "CONNECTED" : "OFFLINE"}
              color={systemHealthy ? "success" : "error"}
              variant="outlined"
              size="small"
              sx={{
                fontWeight: 600,
                borderWidth: 1.5,
                bgcolor: systemHealthy ? "rgba(16, 185, 129, 0.05)" : "rgba(239, 68, 68, 0.05)",
                "& .MuiChip-icon": {
                  fontSize: 18,
                },
              }}
            />
          </Tooltip>

          {/* LLM Provider Selector */}
          <Box display="flex" alignItems="center" gap={1}>
            <RobotIcon fontSize="small" color="action" />
            <FormControl size="small" variant="outlined">
              <Select
                value={llmProvider}
                onChange={handleProviderChange}
                sx={{
                  height: 32,
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  borderRadius: 2,
                  "& .MuiOutlinedInput-notchedOutline": {
                    borderColor: "divider",
                  },
                }}
              >
                <MenuItem value="gemini">Google Gemini 1.5 Pro</MenuItem>
                <MenuItem value="openai" disabled>OpenAI GPT-4o (Config-disabled)</MenuItem>
                <MenuItem value="groq">Groq Llama 3.3 70B</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {/* Theme Toggle Button */}
          <Tooltip title={themeMode === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}>
            <IconButton onClick={toggleThemeMode} color="inherit" size="medium" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 0.75 }}>
              {themeMode === "light" ? <DarkModeIcon fontSize="small" /> : <LightModeIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default TopBar;
