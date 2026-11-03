import os
import httpx
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("FB_PAGE_ACCESS_TOKEN")
if not token:
    print("❌ ERROR: FB_PAGE_ACCESS_TOKEN is not set in .env")
    exit(1)

print(f"Token (first 10 chars): {token[:10]}...")

# Gọi API me?fields=id,name để kiểm tra token
url = f"https://graph.facebook.com/v19.0/me?fields=id,name&access_token={token}"

try:
    resp = httpx.get(url)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Request failed: {e}")
