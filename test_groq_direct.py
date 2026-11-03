import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
GROQ_MODEL = "llama-3.1-8b-instant"

async def test():
    if not GROQ_API_KEYS:
        print("No keys found")
        return
    
    # Let's recreate the messages for Test 4
    system_prompt = """You are the professional, friendly, and expert AI Assistant for 'Easy Trip & Visa Co. Ltd' ...
    
    OUTPUT: Return ONLY a valid JSON object. No markdown wrapping or conversational text outside the JSON.
    {
      "reply_message": "...",
      "extracted_data": {
        "ho_ten": "..."
      },
      "current_phase": "CONSULTING",
      "is_complete": false
    }"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Hi, I am from the US, currently in Nha Trang. My visa expires on 04/06. I want to book a visa run."}
    ]
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEYS[0]}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            print("Status Code:", r.status_code)
            print("Response:", r.text)
        except Exception as e:
            print("Exception:", e)

if __name__ == "__main__":
    asyncio.run(test())
