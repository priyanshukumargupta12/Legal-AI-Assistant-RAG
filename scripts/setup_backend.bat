@echo off
REM =============================================================
REM setup_backend.bat — One-time backend environment setup
REM =============================================================
REM Run this script ONCE to set up the Python virtual environment
REM and install all backend dependencies.
REM
REM Prerequisites:
REM   - Python 3.12 installed and on PATH
REM   - pip available
REM =============================================================

echo [Legal AI Assistant] Setting up backend...
echo.

REM Check Python version
python --version
IF ERRORLEVEL 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Please install Python 3.12 from https://python.org
    pause
    exit /b 1
)

REM Navigate to backend directory
cd /d "%~dp0..\backend"

REM Create virtual environment
echo Creating Python virtual environment...
python -m venv venv
IF ERRORLEVEL 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install all dependencies
echo Installing backend dependencies (this may take several minutes)...
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo ERROR: Failed to install dependencies. Check requirements.txt.
    pause
    exit /b 1
)

REM Copy .env.example to .env if .env doesn't exist
IF NOT EXIST ".env" (
    copy .env.example .env
    echo.
    echo IMPORTANT: .env file created from template.
    echo Please edit backend\.env and add your API keys before starting.
)

echo.
echo [SUCCESS] Backend setup complete!
echo Next step: Edit backend\.env with your API keys, then run start_backend.bat
echo.
pause
