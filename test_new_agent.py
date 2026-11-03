import asyncio
from ai_agent import process_chat

async def run_tests():
    # Test case 1: Vietnamese greeting asking for Visa Run price
    test_1 = [
        {"role": "user", "content": "Xin chào, cho mình hỏi giá visa run đi Lào từ Nha Trang với?"}
    ]
    print("\n--- TEST 1: Vietnamese price query ---")
    res1 = await process_chat(test_1)
    print(f"Phase: {res1.current_phase}")
    print(f"Reply:\n{res1.reply_message}")
    print(f"Extracted: {res1.extracted_data.model_dump()}")

    # Test case 2: Russian greeting asking about Cambodia visa run
    test_2 = [
        {"role": "user", "content": "Привет! Сколько стоит визаран в Камбоджу на 90 дней?"}
    ]
    print("\n--- TEST 2: Russian Cambodia query ---")
    res2 = await process_chat(test_2)
    print(f"Phase: {res2.current_phase}")
    print(f"Reply:\n{res2.reply_message}")
    print(f"Extracted: {res2.extracted_data.model_dump()}")

    # Test case 3: English chat declaring Russian nationality (should switch to Russian)
    test_3 = [
        {"role": "user", "content": "Hello, I want to book a visa run. I am Russian."}
    ]
    print("\n--- TEST 3: English chat declaring Russian nationality ---")
    res3 = await process_chat(test_3)
    print(f"Phase: {res3.current_phase}")
    print(f"Reply:\n{res3.reply_message}")
    print(f"Extracted: {res3.extracted_data.model_dump()}")

    # Test case 4: US customer, visa expires on 04/06 (should calculate 02/06)
    test_4 = [
        {"role": "user", "content": "Hi, I am from the US, currently in Nha Trang. My visa expires on 04/06. I want to book a visa run."}
    ]
    print("\n--- TEST 4: US customer with visa expiring on 04/06 ---")
    res4 = await process_chat(test_4)
    print(f"Phase: {res4.current_phase}")
    print(f"Reply:\n{res4.reply_message}")
    print(f"Extracted: {res4.extracted_data.model_dump()}")

if __name__ == "__main__":
    asyncio.run(run_tests())
