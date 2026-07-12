@echo off
REM =============================================================
REM start_backend.bat — Start the FastAPI backend server
REM =============================================================
REM Activates the virtual environment and starts Uvicorn.
REM API available at: http://localhost:8000
REM API docs at:      http://localhost:8000/docs
REM =============================================================

echo [Legal AI Assistant] Starting backend server...
cd /d "%~dp0..\backend"
call venv\Scripts\activate.bat
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
