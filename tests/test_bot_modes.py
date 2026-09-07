import asyncio
import os
import sys
import unittest

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_store import memory_store
from main import process_omnichannel_logic, set_system_bot_mode, get_system_bot_mode

class TestBotModes(unittest.IsolatedAsyncioTestCase):

    async def test_global_bot_mode_toggle(self):
        print("\n======================================================================")
        print("🧪 KIỂM THỬ CÔNG TẮC BẬT / TẮT CHATBOT TOÀN HỆ THỐNG")
        print("======================================================================")

        # 1. Mặc định là AUTO
        memory_store["GLOBAL_BOT_MODE"] = "auto"
        mode_data = await get_system_bot_mode()
        self.assertEqual(mode_data["global_mode"], "auto")
        print("✅ [Test 1] Trạng thái mặc định: AUTO")

        # 2. Chuyển sang TẮT (OFF / MANUAL)
        memory_store["GLOBAL_BOT_MODE"] = "off"
        reply, img = await process_omnichannel_logic("test_user_123", "Telegram", "Cho mình hỏi giá đi visarun", "telegram_test_user_123")
        self.assertIsNone(reply)
        self.assertIsNone(img)
        print("✅ [Test 2] Khi Chế độ toàn hệ thống là OFF -> Bot KHÔNG tự động trả lời khách thật")

        # 3. Chuyển sang CO-PILOT (Dự thảo nháp)
        memory_store["GLOBAL_BOT_MODE"] = "copilot"
        reply, img = await process_omnichannel_logic("test_user_123", "Telegram", "Cho mình hỏi giá đi visarun", "telegram_test_user_123")
        self.assertIsNone(reply)  # Không gửi trực tiếp cho khách
        draft = memory_store.get("telegram_test_user_123_draft")
        self.assertTrue(bool(draft))
        print(f"✅ [Test 3] Khi Chế độ toàn hệ thống là CO-PILOT -> Bot tạo bản nháp: '{draft[:60]}...'")

        # 4. Chuyển sang BẬT (AUTO)
        memory_store["GLOBAL_BOT_MODE"] = "auto"
        reply, img = await process_omnichannel_logic("test_user_123", "Telegram", "Cho mình hỏi giá đi visarun", "telegram_test_user_123")
        self.assertIsNotNone(reply)
        print(f"✅ [Test 4] Khi BẬT AUTO trở lại -> Bot tự động phản hồi: '{reply[:60]}...'")

        print("======================================================================")
        print("🎉 TẤT CẢ CÁC CHẾ ĐỘ BẬT / TẮT / COPILOT HOẠT ĐỘNG HOÀN HẢO 100%!")
        print("======================================================================")

if __name__ == "__main__":
    unittest.main()
