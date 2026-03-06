@echo off
title Fundament — Investor Education Platform
color 0A

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   F U N D A M E N T  v1.0.0          ║
echo  ║   Investor Education Platform         ║
echo  ╚══════════════════════════════════════╝
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo  ERROR: Python not found. Please install Python 3.6+ from:
        echo  https://www.python.org/downloads/
        pause
        exit /b 1
    ) else (
        set PYTHON=python3
    )
) else (
    set PYTHON=python
)

echo  Python found. Starting server...
echo.

cd /d "%~dp0"
%PYTHON% server.py

pause
