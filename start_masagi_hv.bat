@echo off
title MASAGI HV - Helicopter View
setlocal

rem If already running, just open the browser.
powershell -NoProfile -Command "(New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',8010)" >nul 2>&1
if %errorlevel%==0 (
  echo MASAGI HV is already running - opening browser...
  start http://127.0.0.1:8010
  exit /b 0
)

echo ==========================================
echo   MASAGI HV - Helicopter View
echo   Precise by default
echo ==========================================
echo.
start "" http://127.0.0.1:8010
cd /d "%~dp0app"
python server.py

echo.
echo MASAGI HV server stopped. Press any key to close.
pause >nul
