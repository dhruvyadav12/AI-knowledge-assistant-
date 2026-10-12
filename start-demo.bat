@echo off
title AI Knowledge Assistant - Live Demo Starter
echo =======================================================
echo    AI Knowledge Assistant - Live Interview Demo Starter
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Starting Backend (FastAPI on http://localhost:8000)...
start "AI Knowledge Assistant - Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\activate && uvicorn app.main:app --port 8000"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Frontend (React on http://localhost:5173)...
start "AI Knowledge Assistant - Frontend" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"

timeout /t 4 /nobreak >nul

echo [3/3] Starting Cloudflare Tunnel for Live Demo URL...
echo Look for the *.trycloudflare.com link in the new window!
start "AI Knowledge Assistant - Public Live Tunnel" cmd /k "npx.cmd cloudflared tunnel --url http://localhost:5173"

echo.
echo =======================================================
echo  All services are running!
echo  1. Local App: http://localhost:5173
echo  2. Copy the "https://....trycloudflare.com" link from
echo     the Tunnel window to send to your interviewer!
echo =======================================================
pause
