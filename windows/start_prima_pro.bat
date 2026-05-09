@echo off
title PRIMA PRO - Launcher
color 0A

echo.
echo  ================================================
echo   PRIMA PRO - Algorithmic Trading System
echo  ================================================
echo.

:: ── Verify Python ────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Download from: https://python.org
    pause
    exit /b 1
)
echo [OK] Python found.

:: ── Verify Node ──────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found.
    echo Download from: https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found.

:: ── Paths ─────────────────────────────────────────────────────
set BOT_DIR=C:\Users\ADMIN\MMBOT\PRIMA_trading_bot
set WEBSITE_DIR=C:\Users\ADMIN\MMBOT\PRIMA_trading_bot\website

echo  Bot folder    : %BOT_DIR%
echo  Website folder: %WEBSITE_DIR%
echo.

:: ── Verify folders exist ──────────────────────────────────────
if not exist "%BOT_DIR%" (
    echo [ERROR] Bot folder not found: %BOT_DIR%
    pause
    exit /b 1
)

if not exist "%WEBSITE_DIR%" (
    echo [ERROR] Website folder not found: %WEBSITE_DIR%
    pause
    exit /b 1
)

:: ── Step 1: Flask Dashboard ───────────────────────────────────
echo [1/4] Starting Flask Dashboard on http://localhost:5000 ...
start "Flask Dashboard" cmd /k "cd /d %BOT_DIR%\dashboard && python flask_dashboard.py"
timeout /t 3 /nobreak >nul

:: ── Step 2: Trading Bot ───────────────────────────────────────
echo [2/4] Starting Trading Bot ...
start "Trading Bot" cmd /k "cd /d %BOT_DIR% && python main.py"
timeout /t 3 /nobreak >nul

:: ── Step 3: npm install (first time only) ─────────────────────
echo [3/4] Checking website node_modules ...
if not exist "%WEBSITE_DIR%\node_modules" (
    echo      Running npm install - this takes 1-2 minutes first time...
    cd /d "%WEBSITE_DIR%"
    npm install
)

:: ── Step 4: React Website ─────────────────────────────────────
echo [4/4] Starting React Website on http://localhost:5173 ...
start "React Website" cmd /k "cd /d %WEBSITE_DIR% && npm run dev"
timeout /t 5 /nobreak >nul

:: ── Open browser ──────────────────────────────────────────────
echo.
echo  ================================================
echo   ALL SERVICES STARTED
echo  ================================================
echo   Dashboard : http://localhost:5000
echo   Website   : http://localhost:5173
echo  ================================================
echo.
echo  Opening browser...
start "" "http://localhost:5173"

echo.
echo  All 3 windows are open. This window can be closed.
echo  Press any key to STOP all services.
pause >nul

taskkill /FI "WINDOWTITLE eq Flask Dashboard*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Trading Bot*"     /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq React Website*"   /F >nul 2>&1
echo Done. All services stopped.
timeout /t 2 /nobreak >nul
