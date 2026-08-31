@echo off
title Kaveri Stays

echo ========================================
echo       KAVERI STAYS - STARTING
echo ========================================
echo.

REM Start FastAPI Backend
start "Kaveri Stays API" cmd /k "cd /d C:\kaveri project && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM Wait for backend
timeout /t 4 /nobreak >nul

REM Start Frontend on port 5173
start "Kaveri Stays Frontend" cmd /k "cd /d C:\kaveri project\frontend && python -m http.server 5173"

REM Wait for frontend
timeout /t 3 /nobreak >nul

REM Open Kaveri Stays
start "" "http://127.0.0.1:5173"

echo.
echo ========================================
echo       KAVERI STAYS IS RUNNING
echo ========================================
echo.
echo Frontend : http://127.0.0.1:5173
echo Backend  : http://127.0.0.1:8000
echo API Docs : http://127.0.0.1:8000/docs
echo.
pause