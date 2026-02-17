#!/bin/bash
# XL Axiata Manager Bot - Linux/Mac/Termux Launcher
# ==================================================

echo ""
echo "================================================"
echo "   XL Axiata Manager - Telegram Bot"
echo "================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 tidak ditemukan!"
    echo "Install Python3 terlebih dahulu:"
    echo "  - Ubuntu/Debian: sudo apt install python3"
    echo "  - Termux: pkg install python"
    echo "  - macOS: brew install python3"
    echo ""
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "WARNING: File .env tidak ditemukan!"
    echo "Jalankan setup terlebih dahulu: python3 setup.py"
    echo ""
    exit 1
fi

# Run the bot
echo "Starting bot..."
echo ""
python3 run_bot.py
