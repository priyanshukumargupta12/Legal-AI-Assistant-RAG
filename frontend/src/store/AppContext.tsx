/**
 * store/AppContext.tsx
 * ====================
 * React Context for global application state and theme management.
 *
 * Manages:
 *   - Sidebar open/collapsed state
 *   - Active LLM Provider
 *   - System connectivity health checker (polling /health)
 *   - Dynamic Material UI Dark/Light Theme Switching
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { getTheme } from '../theme/theme';
import axios from 'axios';

interface AppState {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  llmProvider: string;
  setLlmProvider: (provider: string) => void;
  systemHealthy: boolean;
  setSystemHealthy: (healthy: boolean) => void;
  themeMode: 'light' | 'dark';
  toggleThemeMode: () => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [llmProvider, setLlmProvider] = useState('gemini');
  const [systemHealthy, setSystemHealthy] = useState(true);
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme_mode');
    return (saved as 'light' | 'dark') || 'dark';
  });

  useEffect(() => {
    localStorage.setItem('theme_mode', themeMode);
  }, [themeMode]);

  // Ping backend to check health
  useEffect(() => {
    const checkHealth = async () => {
      // In development, the proxy is used. Ping '/health' (configured in vite.config.ts)
      const apiEnvBase = (import.meta as any).env.VITE_API_BASE_URL;
      const pingUrl = apiEnvBase ? `${apiEnvBase.replace('/api/v1', '')}/health` : '/health';
      try {
        const response = await axios.get(pingUrl, { timeout: 5000 });
        const status = response.data?.status;
        setSystemHealthy(status === 'healthy' || status === 'degraded');
        if (response.data?.services?.llm_provider) {
          setLlmProvider(response.data.services.llm_provider);
        }
      } catch (err) {
        setSystemHealthy(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // check health every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const toggleThemeMode = () => {
    setThemeMode((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const activeTheme = getTheme(themeMode);

  return (
    <AppContext.Provider value={{
      sidebarOpen,
      setSidebarOpen,
      llmProvider,
      setLlmProvider,
      systemHealthy,
      setSystemHealthy,
      themeMode,
      toggleThemeMode,
    }}>
      <ThemeProvider theme={activeTheme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </AppContext.Provider>
  );
};

export const useAppContext = (): AppState => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useAppContext must be used within AppProvider');
  return context;
};
