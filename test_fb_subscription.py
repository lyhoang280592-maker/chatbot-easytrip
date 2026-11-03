import os
import httpx
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("FB_PAGE_ACCESS_TOKEN")
if not token:
    print("❌ ERROR: FB_PAGE_ACCESS_TOKEN is not set in .env")
    exit(1)

# Page ID from your screenshot
page_id = "944798045391211"

async def main():
    # 1. Kiểm tra thông tin Token và Page
    print("Checking token and subscription status...")
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
