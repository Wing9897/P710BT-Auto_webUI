@echo off
echo Starting Brother Label Printer Web Tool...
echo.

REM Start backend in a new window
start "Backend - FastAPI" cmd /k "cd /d %~dp0backend && uvicorn app.main:app --reload --port 8000"

REM Wait a moment for backend to start
timeout /t 2 /nobreak >nul

REM Start frontend in a new window
start "Frontend - Vite" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Both servers started in separate windows.
echo Close those windows to stop the servers.
pause
