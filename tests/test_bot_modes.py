import asyncio
import os
import sys
import unittest

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_store import memory_store
from main import (
    process_omnichannel_logic,
    get_system_bot_modes,
    get_platform_bot_mode,
    normalize_platform_key,
    get_effective_bot_mode
)

class TestBotModes(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Reset memory_store trạng thái trước mỗi test
        memory_store.clear()
        memory_store["GLOBAL_BOT_MODE"] = "auto"

    async def test_global_bot_mode_toggle(self):
        print("\n======================================================================")
        print("🧪 KIỂM THỬ CÔNG TẮC BẬT / TẮT CHATBOT TOÀN HỆ THỐNG")
        print("======================================================================")

        # 1. Mặc định là AUTO
        memory_store["GLOBAL_BOT_MODE"] = "auto"
        mode_data = await get_system_bot_modes()
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

    async def test_per_platform_bot_mode_toggle(self):
        print("\n======================================================================")
        print("🧪 KIỂM THỬ BẬT / TẮT / COPILOT CHO TỪNG MẠNG XÃ HỘI RIÊNG BIỆT")
        print("======================================================================")

        # Chuẩn hoá platform keys
        self.assertEqual(normalize_platform_key("tg"), "telegram")
        self.assertEqual(normalize_platform_key("Telegram"), "telegram")
        self.assertEqual(normalize_platform_key("fb"), "facebook")
        self.assertEqual(normalize_platform_key("Meta"), "facebook")
        self.assertEqual(normalize_platform_key("web"), "website")
        self.assertEqual(normalize_platform_key("Zalo"), "zalo")
        print("✅ [Test 5] Chuẩn hoá tên nền tảng (telegram, zalo, facebook, website) chính xác!")

        # Kịch bản:
        # - Telegram: OFF
        # - Zalo: COPILOT
        # - Facebook: OFF
        # - Website: AUTO
        memory_store["GLOBAL_BOT_MODE"] = "auto"
        memory_store["BOT_MODE_TELEGRAM"] = "off"
        memory_store["BOT_MODE_ZALO"] = "copilot"
        memory_store["BOT_MODE_FACEBOOK"] = "off"
        memory_store["BOT_MODE_WEBSITE"] = "auto"

        # Kiểm tra API trả về
        mode_data = await get_system_bot_modes()
        self.assertEqual(mode_data["platforms"]["telegram"], "off")
        self.assertEqual(mode_data["platforms"]["zalo"], "copilot")
        self.assertEqual(mode_data["platforms"]["facebook"], "off")
        self.assertEqual(mode_data["platforms"]["website"], "auto")
        print("✅ [Test 6] API bot-modes trả về đúng trạng thái riêng của 4 nền tảng")

        # 1. Thử nghiệm trên Telegram (Mode: OFF) -> Không trả lời
        tg_reply, _ = await process_omnichannel_logic("tg_user_1", "Telegram", "Chào bot", "telegram_tg_user_1")
        self.assertIsNone(tg_reply)
        self.assertIsNone(memory_store.get("telegram_tg_user_1_draft"))
        print("✅ [Test 7] Telegram (OFF): Bot tắt hoàn toàn, không trả lời tự động.")

        # 2. Thử nghiệm trên Zalo (Mode: COPILOT) -> Tạo nháp, không gửi khách
        zalo_reply, _ = await process_omnichannel_logic("zalo_user_1", "Zalo", "Tư vấn visarun giúp mình", "zalo_zalo_user_1")
        self.assertIsNone(zalo_reply)
        zalo_draft = memory_store.get("zalo_zalo_user_1_draft")
        self.assertTrue(bool(zalo_draft))
        print(f"✅ [Test 8] Zalo (COPILOT): Bot tạo dự thảo nháp thành công: '{zalo_draft[:50]}...'")

        # 3. Thử nghiệm trên Facebook (Mode: OFF) -> Không trả lời
        fb_reply, _ = await process_omnichannel_logic("fb_user_1", "Facebook", "Xin chào shop", "facebook_fb_user_1")
        self.assertIsNone(fb_reply)
        print("✅ [Test 9] Facebook (OFF): Bot tắt hoàn toàn theo cấu hình mạng xã hội riêng.")

        # 4. Thử nghiệm trên Website (Mode: AUTO) -> Tự động trả lời bình thường
        web_reply, _ = await process_omnichannel_logic("web_user_1", "Website", "Xin chào, mình cần tư vấn visa", "website_web_user_1")
        self.assertIsNotNone(web_reply)
        print(f"✅ [Test 10] Website (AUTO): Bot tự động trả lời khách: '{web_reply[:50]}...'")

        # 5. Kiểm thử độ ưu tiên của phiên chat cá nhân (Session override)
        # Phiên telegram_vip được gán mode = 'auto' dù Telegram đang bị tắt toàn kênh
        memory_store["telegram_vip_mode"] = "auto"
        self.assertEqual(get_effective_bot_mode("telegram_vip", "Telegram"), "auto")
        vip_reply, _ = await process_omnichannel_logic("vip", "Telegram", "Xin chào tư vấn cho tôi", "telegram_vip")
        self.assertIsNotNone(vip_reply)
        print("✅ [Test 11] Phân cấp ưu tiên: Phiên chat riêng lẻ > Kênh mạng xã hội > Toàn hệ thống hoạt động chuẩn xác 100%!")

        print("======================================================================")
        print("🎉 TẤT CẢ TEST BẬT / TẮT TỪNG MẠNG XÃ HỘI HOẠT ĐỘNG HOÀN HẢO 100%!")
        print("======================================================================")

if __name__ == "__main__":
    unittest.main()
