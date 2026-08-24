import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def main():
    if not API_ID or not API_HASH:
        print("LỖI: Bạn chưa cài đặt TELEGRAM_API_ID và TELEGRAM_API_HASH trong file .env!")
        print("Vui lòng vào my.telegram.org để lấy và thêm vào .env trước khi chạy lệnh này.")
        return

    print("Bắt đầu đăng nhập tài khoản Telegram cá nhân (UserBot)...")
    client = TelegramClient('scraper_v2', int(API_ID), API_HASH)
    
    # Khởi động và yêu cầu SĐT, OTP
    await client.start()
    
    print("\n✅ Đăng nhập thành công! Hệ thống đã tạo file 'scraper_v2.session'.")
    print("Bây giờ bạn có thể khởi động server FastAPI bình thường.")

if __name__ == "__main__":
    asyncio.run(main())
