import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# User who sent 'hi' and 'tôi muốn visarun'
CHAT_ID = "725096837"

async def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "Hello from test script! Bot is starting to reply."
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload)
        print("Status Code:", res.status_code)
        print("Response:", res.text)

if __name__ == "__main__":
    asyncio.run(main())
