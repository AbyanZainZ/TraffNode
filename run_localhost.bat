@echo off
title TraffNode Engine - Localhost Dashboard (Port 8888)
cd /d "%~dp0"

echo ==============================================================================
echo        TRAFFNODE ENGINE - LOCALHOST DEVELOPMENT LAUNCHER
echo ==============================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di PATH sistem. Harap install Python 3.10+.
    pause
    exit /b 1
)

if not exist "venv\" (
    echo [1/2] Membuat virtual environment...
    python -m venv venv
)

echo [2/2] Memeriksa dependensi...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo ==============================================================================
echo Dashboard Running at: http://127.0.0.1:8888
echo Tekan Ctrl + C untuk mematikan server.
echo ==============================================================================
echo.

python app.py
pause
