#!/usr/bin/env python3
"""
Script untuk mendapatkan Channel ID Telegram
Simpan sebagai: get_channel_id.py
"""

import asyncio
import sys

try:
    from telegram import Bot
except ImportError:
    print("Error: python-telegram-bot tidak terinstall")
    print("Install dengan: pip install python-telegram-bot")
    sys.exit(1)

async def get_channel_id(bot_token, channel_username):
    """Get channel ID from username"""
    bot = Bot(token=bot_token)
    
    try:
        # Untuk public channel
        chat = await bot.get_chat(chat_id=channel_username)
        
        print("\n" + "=" * 60)
        print("✅ CHANNEL DITEMUKAN!")
        print("=" * 60)
        print(f"Title       : {chat.title}")
        print(f"Type        : {chat.type}")
        if chat.username:
            print(f"Username    : @{chat.username}")
        print(f"Channel ID  : {chat.id}")
        print("=" * 60)
        
        print("\n📋 COPY INI KE FILE .env:")
        print("-" * 60)
        print(f"REQUIRED_CHANNEL={channel_username}")
        print(f"CHANNEL_ID={chat.id}")
        print("-" * 60)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR MENDAPATKAN CHANNEL ID")
        print("=" * 60)
        print(f"Error: {e}")
        print("\n💡 TIPS:")
        print("-" * 60)
        print("1. Pastikan channel adalah PUBLIC")
        print("   Atau bot sudah menjadi ADMIN di channel private")
        print("")
        print("2. Format username harus benar:")
        print("   ✅ Benar  : @singularityx2")
        print("   ❌ Salah  : singularityx2")
        print("")
        print("3. Untuk private channel:")
        print("   - Buka channel settings")
        print("   - Pilih 'Administrators'")
        print("   - Tambahkan bot sebagai admin")
        print("   - Minimal permission: bisa kosong semua")
        print("-" * 60)
        
        return False

async def test_membership(bot_token, channel_id, user_id):
    """Test if user is member of channel"""
    bot = Bot(token=bot_token)
    
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        
        print("\n" + "=" * 60)
        print("✅ TEST MEMBERSHIP BERHASIL!")
        print("=" * 60)
        print(f"User        : {member.user.first_name}")
        print(f"User ID     : {member.user.id}")
        print(f"Status      : {member.status}")
        print("=" * 60)
        
        if member.status in ['member', 'administrator', 'creator']:
            print("\n✅ User adalah member channel")
        else:
            print("\n❌ User BUKAN member channel")
            print(f"   Status: {member.status}")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR TEST MEMBERSHIP")
        print("=" * 60)
        print(f"Error: {e}")
        print("\n💡 TIPS:")
        print("-" * 60)
        print("1. Pastikan Channel ID benar")
        print("2. Untuk private channel, bot harus jadi admin")
        print("3. User ID harus benar (angka)")
        print("-" * 60)
        
        return False

def print_header():
    """Print script header"""
    print("=" * 60)
    print("  TELEGRAM CHANNEL ID FINDER & TESTER")
    print("  Script untuk mendapatkan Channel ID")
    print("=" * 60)

def print_menu():
    """Print menu options"""
    print("\n📋 MENU:")
    print("-" * 60)
    print("1. Get Channel ID dari username")
    print("2. Test Channel Membership")
    print("3. Exit")
    print("-" * 60)

async def main():
    """Main function"""
    print_header()
    
    while True:
        print_menu()
        choice = input("\nPilih menu (1-3): ").strip()
        
        if choice == "1":
            print("\n📍 GET CHANNEL ID")
            print("-" * 60)
            
            bot_token = input("Masukkan Bot Token: ").strip()
            if not bot_token:
                print("❌ Bot token tidak boleh kosong!")
                continue
            
            channel_username = input("Masukkan Channel Username (contoh: @singularityx2): ").strip()
            if not channel_username:
                print("❌ Username tidak boleh kosong!")
                continue
            
            # Add @ if not present
            if not channel_username.startswith("@"):
                channel_username = "@" + channel_username
            
            print("\n⏳ Mengambil informasi channel...")
            success = await get_channel_id(bot_token, channel_username)
            
            if success:
                print("\n✅ Berhasil! Sekarang Anda bisa:")
                print("   1. Copy Channel ID ke file .env")
                print("   2. Test membership dengan menu 2")
            
        elif choice == "2":
            print("\n🧪 TEST CHANNEL MEMBERSHIP")
            print("-" * 60)
            
            bot_token = input("Masukkan Bot Token: ").strip()
            if not bot_token:
                print("❌ Bot token tidak boleh kosong!")
                continue
            
            channel_id = input("Masukkan Channel ID (contoh: -1002428095730): ").strip()
            if not channel_id:
                print("❌ Channel ID tidak boleh kosong!")
                continue
            
            # Validate channel ID format
            try:
                channel_id_int = int(channel_id)
            except ValueError:
                print("❌ Channel ID harus berupa angka!")
                print("   Format: -1002428095730 (dengan minus di depan)")
                continue
            
            user_id = input("Masukkan User ID untuk test (your Telegram user ID): ").strip()
            if not user_id:
                print("❌ User ID tidak boleh kosong!")
                continue
            
            try:
                user_id_int = int(user_id)
            except ValueError:
                print("❌ User ID harus berupa angka!")
                continue
            
            print("\n⏳ Testing membership...")
            await test_membership(bot_token, channel_id_int, user_id_int)
            
        elif choice == "3":
            print("\n👋 Terima kasih! Goodbye!")
            break
        
        else:
            print("\n❌ Pilihan tidak valid! Pilih 1-3.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Program dihentikan oleh user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
