@echo off
REM =============================================================
REM setup_frontend.bat — One-time frontend environment setup
REM =============================================================
REM Run this script ONCE to install all Node.js dependencies.
REM
REM Prerequisites:
REM   - Node.js >= 20 installed and on PATH
REM   - npm >= 10 available
REM =============================================================

echo [Legal AI Assistant] Setting up frontend...
echo.

REM Check Node version
node --version
IF ERRORLEVEL 1 (
    echo ERROR: Node.js is not installed or not on PATH.
    echo Please install Node.js 20+ from https://nodejs.org
    pause
    exit /b 1
)

REM Navigate to frontend directory
cd /d "%~dp0..\frontend"

REM Install dependencies
echo Installing frontend dependencies...
npm install
IF ERRORLEVEL 1 (
    echo ERROR: npm install failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Frontend setup complete!
echo Run start_frontend.bat to launch the development server.
echo.
pause
