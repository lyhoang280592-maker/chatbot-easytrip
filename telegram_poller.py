import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN is not set in .env")
    exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"
WEBHOOK_URL = "http://localhost:8000/telegram/webhook"


async def main():
    print("Starting local Telegram Poller...")
    # Xóa webhook cũ (nếu có) để có thể nhận tin nhắn qua getUpdates
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/deleteWebhook")
        print("Delete webhook result:", res.json())

    offset = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("Listening for new messages from Telegram...")
        while True:
            try:
                # getUpdates với timeout (long polling)
                res = await client.get(
                    f"{API_URL}/getUpdates?offset={offset}&timeout=30"
                )
                data = res.json()
                if data.get("ok"):
                    for update in data["result"]:
                        offset = update["update_id"] + 1
                        # Chuyển tiếp (forward) tin nhắn đến server FastAPI ở cổng 8000
                        try:
                            post_res = await client.post(WEBHOOK_URL, json=update)
                            print(
                                f"Forwarded update {update['update_id']} to localhost:8000 -> Status: {post_res.status_code}"
                            )
                        except Exception as e:
                            print(f"Failed to forward update to local server: {e}")
                            print(
                                "Make sure your FastAPI server is running on port 8000 (python main.py)"
                            )
                else:
                    print(f"Error from Telegram API: {data}")
                    await asyncio.sleep(2)
            except httpx.ReadTimeout:
                # Timeout bình thường của long polling, không cần in lỗi
                pass
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
