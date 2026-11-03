import asyncio
import sys
import traceback
from ai_agent import process_chat

# Cấu hình encoding UTF-8 cho Windows stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def main():
    test_4 = [
        {"role": "user", "content": "Hi, I am from the US, currently in Nha Trang. My visa expires on 04/06. I want to book a visa run."}
    ]
    try:
        res = await process_chat(test_4)
        print("RESULT:")
        print("Reply Message:", res.reply_message)
        print("Extracted Data:", res.extracted_data.model_dump())
        print("Current Phase:", res.current_phase)
    except Exception as e:
        print("CRASHED:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
