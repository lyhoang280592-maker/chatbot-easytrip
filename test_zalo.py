import asyncio
import os
import dotenv

dotenv.load_dotenv()
import main

async def test():
    token = await main.get_zalo_access_token()
    print('Token:', token)
    if token:
        # Just to see if it makes a request without failing
        await main.send_zalo_message('test_user', 'Hello from bot')
    print('Done')

if __name__ == "__main__":
    asyncio.run(test())
