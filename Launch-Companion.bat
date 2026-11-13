@echo off
title JM Vertex - AI Desktop Companion
color 0B

echo ======================================================================
echo   JM VERTEX TECHNOLOGIES - AI DESKTOP COMPANION (TEST RUNNER)
echo   Module: Windows Automation & Universal Voice App Launcher
echo   Developer: Logeshwaran D
echo ======================================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found on your system PATH!
    echo Please install Python 3.10+ from python.org or Microsoft Store.
    pause
    exit /b 1
)

:: 2. Check Node.js installation
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not found on your system PATH!
    echo Please install Node.js 18+ from nodejs.org.
    pause
    exit /b 1
)

echo [*] Starting Python Universal Automation Backend on port 8000...
start /b "" python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 > nul 2>&1

:: Wait 2 seconds for backend to start
timeout /t 2 /nobreak > nul

echo [*] Launching AI Desktop Companion...
cd /d "%~dp0desktop"

:: If dist does not exist or node_modules missing, install and build
if not exist "node_modules" (
    echo [*] First-time setup: installing dependencies...
    call npm install
)

if not exist "dist" (
    echo [*] First-time setup: building frontend...
    call npm run build
)

echo [*] Starting Desktop Companion Application...
call npm run app

echo.
echo [*] Shutting down background automation engine...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a > nul 2>&1
)
echo Done.
pause
