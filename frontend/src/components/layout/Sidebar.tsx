/**
 * components/layout/Sidebar.tsx
 * ==============================
 * Collapsible navigation sidebar drawer.
 *
 * Provides links to all pages: Dashboard, Dataset, Data Processing,
 * Ask AI, Search Results, Document Viewer, Evaluation, History, and Pipeline Monitor.
 */

import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Box,
  Divider,
  IconButton,
  useTheme,
  Tooltip,
} from "@mui/material";
import {
  Dashboard as DashboardIcon,
  Storage as DatasetIcon,
  Memory as ProcessingIcon,
  Forum as AskAiIcon,
  Search as SearchResultsIcon,
  Visibility as ViewerIcon,
  Assessment as EvaluationIcon,
  GradeOutlined as GoldenSetIcon,
  History as HistoryIcon,
  AccountTree as PipelineIcon,
  ChevronLeft as ChevronLeftIcon,
  Menu as MenuIcon,
} from "@mui/icons-material";
import { useAppContext } from "../../store/AppContext";

const DRAWER_WIDTH = 260;
const COLLAPSED_DRAWER_WIDTH = 70;

const Sidebar: React.FC = () => {
  const theme = useTheme();
  const location = useLocation();
  const { sidebarOpen, setSidebarOpen } = useAppContext();

  const menuItems = [
    { text: "Dashboard", icon: <DashboardIcon />, path: "/" },
    { text: "Dataset", icon: <DatasetIcon />, path: "/dataset" },
    { text: "Data Processing", icon: <ProcessingIcon />, path: "/processing" },
    { text: "Ask AI (Chat)", icon: <AskAiIcon />, path: "/query" },
    { text: "Search Results", icon: <SearchResultsIcon />, path: "/search" },
    { text: "Document Viewer", icon: <ViewerIcon />, path: "/viewer" },
    { text: "Evaluation", icon: <EvaluationIcon />, path: "/evaluation" },
    { text: "Golden Set", icon: <GoldenSetIcon />, path: "/golden" },
    { text: "History", icon: <HistoryIcon />, path: "/history" },
    { text: "Pipeline Monitor", icon: <PipelineIcon />, path: "/pipeline" },
  ];

  const handleToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: sidebarOpen ? DRAWER_WIDTH : COLLAPSED_DRAWER_WIDTH,
        flexShrink: 0,
        "& .MuiDrawer-paper": {
          width: sidebarOpen ? DRAWER_WIDTH : COLLAPSED_DRAWER_WIDTH,
          boxSizing: "border-box",
          overflowX: "hidden",
          transition: theme.transitions.create("width", {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        },
      }}
    >
      {/* Sidebar Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: sidebarOpen ? "space-between" : "center",
          px: 2,
          py: 2,
          minHeight: 64,
        }}
      >
        {sidebarOpen && (
          <Box display="flex" alignItems="center" gap={1}>
            <Box
              sx={{
                width: 8,
                height: 24,
                bgcolor: "primary.main",
                borderRadius: 1,
              }}
            />
            <Typography variant="h6" fontWeight={700} sx={{ letterSpacing: "-0.03em" }}>
              LEGAL assistant
            </Typography>
          </Box>
        )}
        <IconButton onClick={handleToggle}>
          {sidebarOpen ? <ChevronLeftIcon /> : <MenuIcon />}
        </IconButton>
      </Box>

      <Divider />

      {/* Navigation list */}
      <List sx={{ px: 1, py: 2, flexGrow: 1 }}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path;

          return (
            <ListItem key={item.text} disablePadding sx={{ display: "block", mb: 0.5 }}>
              <Tooltip title={!sidebarOpen ? item.text : ""} placement="right">
                <ListItemButton
                  component={Link}
                  to={item.path}
                  selected={isActive}
                  sx={{
                    minHeight: 48,
                    justifyContent: sidebarOpen ? "initial" : "center",
                    px: 2.5,
                    borderRadius: 2,
                    "&.Mui-selected": {
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                      "& .MuiListItemIcon-root": {
                        color: "primary.contrastText",
                      },
                      "&:hover": {
                        bgcolor: "primary.dark",
                      },
                    },
                    "&:hover": {
                      bgcolor: "action.hover",
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: sidebarOpen ? 2 : "auto",
                      justifyContent: "center",
                      color: isActive ? "inherit" : "text.secondary",
                      transition: "color 0.2s",
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  {sidebarOpen && (
                    <ListItemText
                      primary={item.text}
                      primaryTypographyProps={{
                        fontWeight: isActive ? 600 : 500,
                        fontSize: "0.875rem",
                      }}
                    />
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          );
        })}
      </List>

      <Divider />

      {/* Sidebar Footer */}
      <Box sx={{ p: 2, textAlign: sidebarOpen ? "left" : "center" }}>
        {sidebarOpen ? (
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              US Legal & Tax RAG
            </Typography>
            <Typography variant="caption" color="text.disabled" sx={{ fontSize: 10 }}>
              Enterprise Edition v1.0.0
            </Typography>
          </Box>
        ) : (
          <Typography variant="caption" color="text.disabled" fontWeight={700}>
            AI
          </Typography>
        )}
      </Box>
    </Drawer>
  );
};

export default Sidebar;
