import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from ai_agent import process_chat

async def test_prices():
    print("=== TEST 1: Khách hỏi giá E-visa khẩn 1 giờ, 2 giờ, 4 giờ ===")
    messages = [
        {"role": "user", "content": "Cho mình hỏi giá làm E-visa Việt Nam khẩn 1 giờ, 2 giờ và 4 giờ bao nhiêu tiền?"}
    ]
    res = await process_chat(messages)
    print("Bot Response 1:")
    print(res.reply_message)
    print("-" * 50)

    print("\n=== TEST 2: Khách hỏi giá Fast Track sân bay Cam Ranh và Tân Sơn Nhất ===")
    messages2 = [
        {"role": "user", "content": "Bên bạn có dịch vụ Fast track đón ở sân bay Cam Ranh và Tân Sơn Nhất không? Giá thế nào?"}
    ]
    res2 = await process_chat(messages2)
    print("Bot Response 2:")
    print(res2.reply_message)
    print("-" * 50)

    print("\n=== TEST 3: Khách Nga hỏi giá visarun 4 giờ ===")
    messages3 = [
        {"role": "user", "content": "I am Russian. How much is the Russian 4-hour visa run (Single and Multi)?"}
    ]
    res3 = await process_chat(messages3)
    print("Bot Response 3:")
    print(res3.reply_message)
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_prices())
