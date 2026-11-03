import asyncio
from ai_agent import process_chat

async def test_date_calculation():
    # Simulate the exact history in the screenshot
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! Welcome to Easy Trip & Visa. I'm here to help you with your Visarun trip. Could you please tell me your nationality, current city, and visa expiry date?"},
        {"role": "user", "content": "US, Nha Trang, 04/06"}
    ]
    print("\n--- RUNNING CALENDAR CORRECTION TEST ---")
    res = await process_chat(history)
    print(f"Phase: {res.current_phase}")
    print(f"Reply:\n{res.reply_message}")
    print(f"Extracted: {res.extracted_data.model_dump()}")

if __name__ == "__main__":
    asyncio.run(test_date_calculation())
