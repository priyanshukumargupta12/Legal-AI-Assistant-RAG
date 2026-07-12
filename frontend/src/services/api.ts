/**
 * services/api.ts
 * ================
 * Axios HTTP client base instance with interceptors.
 *
 * PURPOSE:
 *   Single Axios instance shared by all service modules.
 *   Configures: base URL, default headers, timeout,
 *   request logging, and error transformation interceptors.
 *
 * TODO: Implement in Milestone 12 (Frontend Pages)
 */

import axios from 'axios';
import { enqueueSnackbar } from 'notistack';

// Base URL from Vite environment variable (falls back to Vite proxy)
const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL ?? '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10 minute timeout (bulk document parsing/embedding can take several minutes)
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    if ((import.meta as any).env.DEV) {
      console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.data ?? '');
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for logging and standardized global error handling
apiClient.interceptors.response.use(
  (response) => {
    if ((import.meta as any).env.DEV) {
      console.log(`[API Response] ${response.config.url}`, response.data);
    }
    return response;
  },
  (error) => {
    let friendlyMessage = 'An unexpected error occurred. Please try again.';

    if (error.response) {
      // Server returned a status code outside the 2xx range
      const responseData = error.response.data;
      friendlyMessage = responseData?.message || responseData?.error || `Error ${error.response.status}: Server issue.`;
      console.error(`[API Response Error] ${error.config?.url} | Status: ${error.response.status}`, responseData);
    } else if (error.request) {
      // Request was made but no response was received
      friendlyMessage = 'Connection error: Unable to reach the Legal Assistant backend.';
      console.error(`[API Network Error] ${error.config?.url}`, error.request);
    } else {
      // Error setting up the request
      friendlyMessage = error.message || friendlyMessage;
      console.error('[API Request Error]', error.message);
    }

    // Trigger notistack snackbar alert globally
    enqueueSnackbar(friendlyMessage, { 
      variant: 'error',
      autoHideDuration: 5000,
    });

    return Promise.reject(error);
  }
);
