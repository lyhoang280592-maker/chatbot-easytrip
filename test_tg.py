import asyncio
import os
import httpx
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def test_bot():
    if not BOT_TOKEN:
        print("❌ Chưa có TELEGRAM_BOT_TOKEN trong file .env")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                print(f"✅ Bot Token hợp lệ! Đang chạy dưới tên: @{data['result']['username']}")
                return True
        print(f"❌ Lỗi Bot Token: {resp.text}")
        return False

async def test_userbot():
    if not API_ID or not API_HASH:
         print("❌ Chưa có API_ID hoặc API_HASH trong file .env")
         return False
    if not os.path.exists("scraper.session"):
        print("❌ File scraper.session không tồn tại. Vui lòng chạy python login_scraper.py để đăng nhập.")
        return False
        
    client = TelegramClient("scraper", int(API_ID), API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ UserBot chưa được ủy quyền (Phiên đăng nhập đã hết hạn). Cần đăng nhập lại.")
            return False
        me = await client.get_me()
        username = f"@{me.username}" if me.username else "Không có username"
        print(f"✅ UserBot hợp lệ! Đang kết nối với tài khoản: {me.first_name} ({username})")
        return True
    except Exception as e:
        print(f"❌ Lỗi UserBot: {repr(e)}")
        return False
    finally:
        await client.disconnect()

async def main():
    print("\n--- KIỂM TRA KẾT NỐI TELEGRAM ---")
    await test_bot()
    print("-" * 30)
    await test_userbot()
    print("---------------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())
