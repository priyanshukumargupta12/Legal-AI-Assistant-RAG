/**
 * theme/theme.ts
 * ==============
 * Material UI custom theme for the Legal AI Assistant.
 *
 * PURPOSE:
 *   Defines the complete visual design system: color palette, typography,
 *   component overrides, and dark mode configuration.
 *
 * DESIGN DECISIONS:
 *   - Dark mode as default (professional legal tool aesthetic)
 *   - Deep navy primary (trust, authority — legal domain appropriate)
 *   - Inter font family (clean, highly legible for dense legal text)
 *   - Rounded corners: subtle (4px) for professional look
 *   - Component overrides: consistent button, card, and table styling
 */

import { createTheme } from "@mui/material/styles";

// ─── Color Palettes ─────────────────────────────────────────────────────────────
const LIGHT_COLORS = {
  primaryMain: "#2563EB",        // Royal blue for high contrast on light background
  primaryDark: "#1D4ED8",
  primaryLight: "#60A5FA",
  secondaryMain: "#D97706",      // Gold accent
  secondaryDark: "#B45309",
  secondaryLight: "#FBBF24",
  successMain: "#059669",
  errorMain: "#DC2626",
  warningMain: "#D97706",
  bgDefault: "#F8FAFC",          // Slate-50
  bgPaper: "#FFFFFF",            // White card background
  bgElevated: "#F1F5F9",         // Slate-100
  textPrimary: "#0F172A",        // Slate-900
  textSecondary: "#475569",      // Slate-600
  textDisabled: "#94A3B8",       // Slate-400
  divider: "#E2E8F0",            // Slate-200
} as const;

const DARK_COLORS = {
  primaryMain: "#3B82F6",        // Bright blue for dark mode
  primaryDark: "#1D4ED8",
  primaryLight: "#93C5FD",
  secondaryMain: "#F59E0B",      // Gold accent
  secondaryDark: "#D97706",
  secondaryLight: "#FCD34D",
  successMain: "#10B981",
  errorMain: "#EF4444",
  warningMain: "#F59E0B",
  bgDefault: "#0F172A",          // Slate-900
  bgPaper: "#1E293B",            // Slate-800
  bgElevated: "#334155",         // Slate-700
  textPrimary: "#F1F5F9",        // Slate-100
  textSecondary: "#94A3B8",      // Slate-400
  textDisabled: "#475569",       // Slate-600
  divider: "#334155",            // Slate-700
} as const;

// ─── Theme Creator ────────────────────────────────────────────────────────────
export const getTheme = (mode: "light" | "dark") => {
  const COLORS = mode === "light" ? LIGHT_COLORS : DARK_COLORS;

  return createTheme({
    palette: {
      mode,
      primary: {
        main: COLORS.primaryMain,
        dark: COLORS.primaryDark,
        light: COLORS.primaryLight,
        contrastText: "#FFFFFF",
      },
      secondary: {
        main: COLORS.secondaryMain,
        dark: COLORS.secondaryDark,
        light: COLORS.secondaryLight,
        contrastText: mode === "light" ? "#FFFFFF" : "#0F172A",
      },
      success: { main: COLORS.successMain },
      error: { main: COLORS.errorMain },
      warning: { main: COLORS.warningMain },
      background: {
        default: COLORS.bgDefault,
        paper: COLORS.bgPaper,
      },
      text: {
        primary: COLORS.textPrimary,
        secondary: COLORS.textSecondary,
        disabled: COLORS.textDisabled,
      },
      divider: COLORS.divider,
    },

    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontWeight: 700, fontSize: "2.5rem", letterSpacing: "-0.02em" },
      h2: { fontWeight: 700, fontSize: "2rem", letterSpacing: "-0.01em" },
      h3: { fontWeight: 600, fontSize: "1.75rem" },
      h4: { fontWeight: 600, fontSize: "1.5rem" },
      h5: { fontWeight: 600, fontSize: "1.25rem" },
      h6: { fontWeight: 600, fontSize: "1rem" },
      subtitle1: { fontWeight: 500, fontSize: "0.95rem" },
      subtitle2: { fontWeight: 500, fontSize: "0.875rem", color: COLORS.textSecondary },
      body1: { fontSize: "0.95rem", lineHeight: 1.7 },
      body2: { fontSize: "0.875rem", lineHeight: 1.6, color: COLORS.textSecondary },
      caption: { fontSize: "0.75rem", color: COLORS.textSecondary },
      button: { fontWeight: 600, textTransform: "none", letterSpacing: "0.01em" },
    },

    shape: {
      borderRadius: 8,
    },

    components: {
      // ── Button ──────────────────────────────────────────────────────────────
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            padding: "8px 20px",
            boxShadow: "none",
            "&:hover": { boxShadow: "none" },
          },
          containedPrimary: {
            background: `linear-gradient(135deg, ${COLORS.primaryMain} 0%, ${COLORS.primaryDark} 100%)`,
            "&:hover": {
              background: `linear-gradient(135deg, ${COLORS.primaryDark} 0%, ${mode === 'light' ? '#1E3A8A' : '#1E3A8A'} 100%)`,
            },
          },
        },
      },

      // ── Card ─────────────────────────────────────────────────────────────────
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: `1px solid ${COLORS.divider}`,
            borderRadius: 12,
            backgroundColor: COLORS.bgPaper,
          },
        },
      },

      // ── Paper ────────────────────────────────────────────────────────────────
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            backgroundColor: COLORS.bgPaper,
          },
          elevation1: {
            boxShadow: mode === "light" ? "0 1px 3px rgba(0,0,0,0.1)" : "0 1px 3px rgba(0,0,0,0.4)",
          },
        },
      },

      // ── TextField ────────────────────────────────────────────────────────────
      MuiTextField: {
        defaultProps: {
          variant: "outlined",
          size: "medium",
        },
        styleOverrides: {
          root: {
            "& .MuiOutlinedInput-root": {
              borderRadius: 8,
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: COLORS.primaryMain,
              },
            },
          },
        },
      },

      // ── Chip ─────────────────────────────────────────────────────────────────
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 6,
            fontWeight: 500,
          },
        },
      },

      // ── Table ────────────────────────────────────────────────────────────────
      MuiTableHead: {
        styleOverrides: {
          root: {
            "& .MuiTableCell-head": {
              fontWeight: 600,
              backgroundColor: COLORS.bgElevated,
              color: COLORS.textPrimary,
              borderBottom: `2px solid ${COLORS.divider}`,
            },
          },
        },
      },

      // ── Drawer (sidebar) ────────────────────────────────────────────────────
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: COLORS.bgPaper,
            borderRight: `1px solid ${COLORS.divider}`,
          },
        },
      },

      // ── AppBar ────────────────────────────────────────────────────────────────
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: COLORS.bgPaper,
            borderBottom: `1px solid ${COLORS.divider}`,
            boxShadow: "none",
          },
        },
      },

      // ── LinearProgress ────────────────────────────────────────────────────────
      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            height: 6,
          },
        },
      },
    },
  });
};

export default getTheme;
