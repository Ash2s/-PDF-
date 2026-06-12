@echo off
title PDF Form Filler
cd /d %~dp0..\..
echo ================================
echo   PDF Form Filler
echo ================================
echo.
echo [1/3] Installing deps...
pip install -r requirements.txt
echo.
echo [2/3] Starting server...
set MIMO_API_KEY=sk-cp9r62bgyzngqes4092c1r340weh3xdkm3gkok7mhfqzchxx
start "" python app.py
timeout /t 3 /nobreak >nul
echo.
echo [3/3] Opening browser...
start "" http://localhost:8001
echo.
echo Server: http://localhost:8001
echo Close this window to stop
echo.
pause
