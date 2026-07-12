/**
 * App.tsx
 * ========
 * Root application component with React Router v6 route definitions.
 *
 * PURPOSE:
 *   Defines all application routes using React Router v6.
 *   Each route lazy-loads its page component for performance.
 *   MainLayout wraps all pages with sidebar and topbar.
 *
 * ROUTES:
 *   /            → DashboardPage   (system overview)
 *   /documents   → DocumentsPage   (upload + list)
 *   /query       → QueryPage       (Q&A chat)
 *   /dataset     → DatasetPage     (scan + export)
 *   /evaluation  → EvaluationPage  (golden set + metrics)
 *
 * TODO: Implement full page components in Milestone 12 (Frontend Pages)
 */

import React, { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Box, CircularProgress, Typography } from "@mui/material";

// Lazy-loaded page components (code-splitting for performance)
const MainLayout = lazy(() => import("./layouts/MainLayout"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const DatasetPage = lazy(() => import("./pages/DatasetPage"));
const ProcessingPage = lazy(() => import("./pages/ProcessingPage"));
const QueryPage = lazy(() => import("./pages/QueryPage"));
const SearchResultsPage = lazy(() => import("./pages/SearchResultsPage"));
const ViewerPage = lazy(() => import("./pages/ViewerPage"));
const EvaluationPage = lazy(() => import("./pages/EvaluationPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const PipelinePage = lazy(() => import("./pages/PipelinePage"));
const GoldenSetPage = lazy(() => import("./pages/GoldenSetPage"));

/** Full-screen loading indicator shown during lazy-load suspense. */
const PageLoader: React.FC = () => (
  <Box
    display="flex"
    flexDirection="column"
    alignItems="center"
    justifyContent="center"
    minHeight="80vh"
    gap={2}
  >
    <CircularProgress color="primary" size={40} thickness={4} />
    <Typography variant="body2" color="text.secondary" fontWeight={500}>
      Loading interface...
    </Typography>
  </Box>
);

const App: React.FC = () => {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="dataset" element={<DatasetPage />} />
          <Route path="processing" element={<ProcessingPage />} />
          {/* Legacy route compatibility: redirect to processing page */}
          <Route path="documents" element={<Navigate to="/processing" replace />} />
          <Route path="query" element={<QueryPage />} />
          <Route path="search" element={<SearchResultsPage />} />
          <Route path="viewer" element={<ViewerPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
          <Route path="golden" element={<GoldenSetPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="pipeline" element={<PipelinePage />} />
          {/* Catch-all: redirect to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export default App;
