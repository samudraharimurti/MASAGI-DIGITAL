@echo off
title MASAGI Landing - Review Server
setlocal
cd /d "%~dp0"

rem If the review server is already running, just open the browser.
powershell -NoProfile -Command "(New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',8040)" >nul 2>&1
if %errorlevel%==0 (
  echo Review server already running - opening browser...
  start "" http://localhost:8040
  exit /b 0
)

where python >nul 2>&1
if %errorlevel% neq 0 (
  echo Python not found - opening the page directly from the file instead.
  start "" "%~dp0index.html"
  exit /b 0
)

echo ==========================================
echo   MASAGI Digital - Landing Page Review
echo   http://localhost:8040
echo   Close this window to stop the server.
echo ==========================================
echo.
start "" http://localhost:8040
python -m http.server 8040

echo.
echo Review server stopped. Press any key to close.
pause >nul
