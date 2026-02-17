#!/usr/bin/env python3
"""
Setup script untuk XL Axiata Manager Bot
Compatible dengan Windows, Linux, dan Termux
"""

import os
import sys
import subprocess
import platform

def print_header(text):
    """Print header dengan garis"""
    width = 60
    print("\n" + "="*width)
    print(text.center(width))
    print("="*width + "\n")

def check_python_version():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required. Current version: {version.major}.{version.minor}")
        sys.exit(1)
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")

def install_requirements():
    """Install requirements"""
    print("\nInstalling requirements...")
    
    req_file = "requirements_bot.txt"
    if not os.path.exists(req_file):
        req_file = "requirements.txt"
    
    try:
        # Try with pip
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "--break-system-packages"])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError:
        try:
            # Try without --break-system-packages
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("✅ Requirements installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install requirements: {e}")
            print("\nPlease install manually:")
            print(f"  pip install -r {req_file}")
            return False

def create_env_file():
    """Create .env file if not exists"""
    print("\nChecking .env file...")
    
    if os.path.exists(".env"):
        print("✅ .env file already exists")
        
        # Check if TELEGRAM_BOT_TOKEN exists
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
            if "TELEGRAM_BOT_TOKEN" not in content:
                print("\n⚠️  TELEGRAM_BOT_TOKEN not found in .env")
                print("Adding TELEGRAM_BOT_TOKEN placeholder...")
                
                with open(".env", "a", encoding="utf-8") as f:
                    f.write("\n# Telegram Bot Token\n")
                    f.write("TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE\n")
                
                print("✅ TELEGRAM_BOT_TOKEN placeholder added")
                print("\n⚠️  Please edit .env and add your bot token!")
        return True
    
    print("Creating .env file from template...")
    
    if os.path.exists(".env.template"):
        # Copy from template
        with open(".env.template", "r", encoding="utf-8") as src:
            content = src.read()
        
        with open(".env", "w", encoding="utf-8") as dst:
            dst.write(content)
            dst.write("\n\n# Telegram Bot Token\n")
            dst.write("TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE\n")
        
        print("✅ .env file created from template")
        print("\n⚠️  Please edit .env and add your bot token!")
        return True
    else:
        print("❌ .env.template not found")
        print("\nPlease create .env file manually with required variables")
        return False

def create_user_data_dir():
    """Create data/user_data directory"""
    print("\nCreating data/user_data directory...")
    
    user_data_dir = "data/user_data"
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        print(f"✅ Created {user_data_dir} directory")
    else:
        print(f"✅ {user_data_dir} directory already exists")

def print_system_info():
    """Print system information"""
    print_header("System Information")
    
    print(f"Operating System: {platform.system()}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python Version: {sys.version}")

def print_instructions():
    """Print usage instructions"""
    print_header("Setup Complete!")
    
    print("📋 Next Steps:\n")
    
    print("1. Edit .env file and add your TELEGRAM_BOT_TOKEN:")
    if platform.system() == "Windows":
        print("   notepad .env")
    else:
        print("   nano .env")
    
    print("\n2. Get your bot token from @BotFather on Telegram")
    print("   - Open Telegram and search for @BotFather")
    print("   - Send /newbot and follow instructions")
    print("   - Copy the token and paste it in .env file")
    
    print("\n3. Run the bot:")
    if platform.system() == "Windows":
        print("   python bot_telegram.py")
    else:
        print("   python3 bot_telegram.py")
    
    print("\n4. Open your bot on Telegram and send /start")
    
    print("\n" + "="*60)
    print("For more information, read README.md".center(60))
    print("="*60 + "\n")

def main():
    """Main setup function"""
    print_header("XL Axiata Manager Bot - Setup")
    
    # Print system info
    print_system_info()
    
    # Check Python version
    check_python_version()
    
    # Install requirements
    if not install_requirements():
        print("\n⚠️  Requirements installation failed.")
        print("Please install manually before running the bot.")
    
    # Create .env file
    create_env_file()
    
    # Create user_data directory
    create_user_data_dir()
    
    # Print instructions
    print_instructions()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
