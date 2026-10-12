@echo off
title AI Knowledge Assistant - Live Demo Starter
echo ======================================================================
echo           AI Knowledge Assistant - Live Interview Demo
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Starting Backend (FastAPI on http://localhost:8000)...
start "AI Knowledge Assistant - Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\activate && uvicorn app.main:app --port 8000"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Frontend (React on http://localhost:5173)...
start "AI Knowledge Assistant - Frontend" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"

timeout /t 3 /nobreak >nul

echo [3/3] Fetching Tunnel Password (Your Public IP)...
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content.Trim()"`) do set "TUNNEL_PASS=%%A"

echo.
echo ======================================================================
echo   LIVE DEMO READY!
echo.
echo   Local URL:    http://localhost:5173
echo   Tunnel URL:   https://dhruv-ai-assistant.loca.lt
echo   Password:     %TUNNEL_PASS%
echo ======================================================================
echo.
echo Launching public tunnel window...

start "AI Knowledge Assistant - Public Live Tunnel" cmd /k "echo ====================================================================== & echo  SHARE THIS LINK WITH YOUR INTERVIEWER: & echo  https://dhruv-ai-assistant.loca.lt & echo. & echo  IF THE PAGE ASKS FOR A 'TUNNEL PASSWORD', ENTER: & echo  %TUNNEL_PASS% & echo ====================================================================== & echo. & lt.cmd --port 5173 --subdomain dhruv-ai-assistant"

start http://localhost:5173

echo.
echo You can keep this window open or close it when done.
pause
