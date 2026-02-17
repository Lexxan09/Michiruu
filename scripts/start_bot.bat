@echo off
REM XL Axiata Manager Bot - Windows Launcher
REM ==========================================

echo.
echo ================================================
echo   XL Axiata Manager - Telegram Bot
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python tidak ditemukan!
    echo Silakan install Python 3.8+ dari https://www.python.org
    echo.
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo WARNING: File .env tidak ditemukan!
    echo Jalankan setup terlebih dahulu: python setup.py
    echo.
    pause
    exit /b 1
)

REM Run the bot
echo Starting bot...
echo.
python run_bot.py

pause
