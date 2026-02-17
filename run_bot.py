#!/usr/bin/env python3
"""
Launcher script untuk XL Axiata Manager Bot
Compatible dengan Windows, Linux, dan Termux
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

def print_header():
    """Print header"""
    width = 60
    print("\n" + "="*width)
    print("XL Axiata Manager - Telegram Bot".center(width))
    print("="*width + "\n")

def check_env_file():
    """Check if .env file exists and has bot token"""
    if not os.path.exists(".env"):
        print("❌ File .env tidak ditemukan!")
        print("\nJalankan setup terlebih dahulu:")
        if platform.system() == "Windows":
            print("  python setup.py")
        else:
            print("  python3 setup.py")
        return False
    
    # Check if bot token exists
    with open(".env", "r", encoding="utf-8") as f:
        content = f.read()
        
        if "TELEGRAM_BOT_TOKEN" not in content:
            print("⚠️  TELEGRAM_BOT_TOKEN tidak ditemukan di .env")
            print("\nEdit file .env dan tambahkan bot token:")
            if platform.system() == "Windows":
                print("  notepad .env")
            else:
                print("  nano .env")
            return False
        
        if "YOUR_BOT_TOKEN_HERE" in content:
            print("⚠️  Bot token belum diisi di .env")
            print("\nEdit file .env dan ganti YOUR_BOT_TOKEN_HERE dengan token asli:")
            if platform.system() == "Windows":
                print("  notepad .env")
            else:
                print("  nano .env")
            print("\nCara mendapatkan token:")
            print("  1. Buka @BotFather di Telegram")
            print("  2. Kirim /newbot")
            print("  3. Copy token yang diberikan")
            return False
    
    return True

def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import telegram
        return True
    except ImportError:
        print("⚠️  Dependencies belum terinstall!")
        print("\nInstall dependencies dengan:")
        if platform.system() == "Windows":
            print("  pip install -r requirements_bot.txt")
        else:
            print("  pip install -r requirements_bot.txt --break-system-packages")
        print("\nAtau jalankan:")
        if platform.system() == "Windows":
            print("  python setup.py")
        else:
            print("  python3 setup.py")
        return False

def create_user_data_dir():
    """Create user_data directory if not exists"""
    user_data_dir = Path("user_data")
    if not user_data_dir.exists():
        user_data_dir.mkdir(parents=True)
        print("✅ Created user_data directory")

def run_bot():
    """Run the bot"""
    print("🤖 Starting XL Axiata Manager Bot...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Import and run bot
        import bot_telegram
        bot_telegram.main()
    except KeyboardInterrupt:
        print("\n\n✅ Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error running bot: {e}")
        print("\nJika error berlanjut, coba:")
        print("  1. Pastikan .env sudah benar")
        print("  2. Install ulang dependencies")
        print("  3. Restart bot")
        sys.exit(1)

def main():
    """Main function"""
    print_header()
    
    # Print system info
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}\n")
    
    # Check .env file
    if not check_env_file():
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create user_data directory
    create_user_data_dir()
    
    # Run bot
    run_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✅ Launcher stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
