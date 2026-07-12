/**
 * main.tsx
 * ========
 * React application bootstrap.
 *
 * Renders the root App component inside:
 *   - React.StrictMode (catches subtle bugs in development)
 *   - ThemeProvider (MUI dark theme)
 *   - CssBaseline (resets browser CSS to MUI defaults)
 *   - QueryClientProvider (React Query global cache)
 *   - SnackbarProvider (notistack notifications)
 *   - AppProvider (global state context)
 *   - BrowserRouter (React Router)
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SnackbarProvider } from "notistack";

import App from "./App";
import { AppProvider } from "./store/AppContext";

// React Query client with sensible defaults for a legal AI tool
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,   // 5 minutes — legal docs don't change frequently
      gcTime: 10 * 60 * 1000,      // 10 minutes garbage collection
    },
    mutations: {
      retry: 1,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("Root element #root not found in index.html");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <SnackbarProvider
          maxSnack={3}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          autoHideDuration={4000}
        >
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </SnackbarProvider>
      </AppProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
