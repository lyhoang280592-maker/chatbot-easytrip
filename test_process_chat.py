import asyncio
from ai_agent import process_chat

async def test():
    print("Testing process_chat with message 'usa'...")
    history = [
        {"role": "user", "content": "usa"}
    ]
    try:
        response = await process_chat(history)
        print("--- SUCCESS ---")
        print(f"Reply: {response.reply_message}")
        print(f"Phase: {response.current_phase}")
        print(f"Is Complete: {response.is_complete}")
        if hasattr(response, "extracted_data"):
            data = response.extracted_data
            data_dict = data.model_dump() if hasattr(data, "model_dump") else vars(data)
            print(f"Extracted Data: {data_dict}")
    except Exception as e:
        import traceback
        print("--- FAILED ---")
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
