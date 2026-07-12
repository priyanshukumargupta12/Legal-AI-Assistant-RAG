import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

/**
 * Vite Configuration
 * ==================
 * PURPOSE:
 *   Configures the Vite build tool for the React + TypeScript frontend.
 *
 * KEY FEATURES:
 *   - React plugin: enables JSX fast refresh and JSX transform
 *   - Dev proxy: forwards /api/* requests to FastAPI backend at :8000
 *     (avoids CORS issues during development)
 *   - Path aliases: matches tsconfig.json paths for clean imports
 *   - Build output: dist/ directory with asset chunking
 */
export default defineConfig({
  plugins: [react()],

  /* ─── Path Aliases ─────────────────────────────────────────────────────── */
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
      "@components": resolve(__dirname, "./src/components"),
      "@pages": resolve(__dirname, "./src/pages"),
      "@hooks": resolve(__dirname, "./src/hooks"),
      "@services": resolve(__dirname, "./src/services"),
      "@types": resolve(__dirname, "./src/types"),
      "@utils": resolve(__dirname, "./src/utils"),
      "@theme": resolve(__dirname, "./src/theme"),
      "@store": resolve(__dirname, "./src/store"),
    },
  },

  /* ─── Dev Server ────────────────────────────────────────────────────────── */
  server: {
    port: 5173,
    host: true,
    proxy: {
      // Forward all /api/* requests to the FastAPI backend
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      // Forward /health to the backend
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  /* ─── Preview Server ────────────────────────────────────────────────────── */
  preview: {
    port: 4173,
    host: true,
  },

  /* ─── Build ──────────────────────────────────────────────────────────────── */
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        // Split vendor libraries into separate chunks for better caching
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          "mui-vendor": ["@mui/material", "@mui/icons-material", "@emotion/react", "@emotion/styled"],
          "query-vendor": ["@tanstack/react-query"],
          "axios-vendor": ["axios"],
        },
      },
    },
  },
});
