@echo off
REM =============================================================
REM start_frontend.bat — Start the React frontend dev server
REM =============================================================
REM Starts the Vite development server.
REM Frontend available at: http://localhost:5173
REM =============================================================

echo [Legal AI Assistant] Starting frontend server...
cd /d "%~dp0..\frontend"
npm run dev
