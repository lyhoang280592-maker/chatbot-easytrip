import os
import asyncio
import sys
# Cấu hình encoding UTF-8 cho Windows stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

api_keys_str = os.getenv("GROQ_API_KEYS") or ""
groq_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

async def test_key(key, idx):
    try:
        client = AsyncGroq(api_key=key)
        print(f"Testing Key {idx+1}: {key[:15]}...")
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=10
        )
        print(f"✅ Key {idx+1} is VALID! Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ Key {idx+1} FAILED with error: {e}")
        return False

async def main():
    print(f"Found {len(groq_keys)} keys to test.")
    for idx, key in enumerate(groq_keys):
        await test_key(key, idx)

if __name__ == "__main__":
    asyncio.run(main())
