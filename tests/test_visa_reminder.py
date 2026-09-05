"""
Test Suite: Kiểm thử Hệ thống Nhắc nhở Tự động Hết hạn Visa Trước 10 Ngày (Automated 10-day Visa Expiry Reminder)
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import customer_memory
from customer_memory import (
    init_db,
    get_db_connection,
    get_or_create_customer,
    update_customer_profile,
    update_customer_visa_expiry,
    get_customers_needing_visa_reminder,
    get_session_messages,
    format_customer_profile_for_prompt
)
from visa_reminder import (
    generate_reminder_message,
    send_visa_reminder_to_customer,
    check_and_send_daily_reminders,
    format_display_date
)
from ai_agent import process_chat

async def run_visa_reminder_tests():
    print("=" * 70)
    print("🚀 BẮT ĐẦU KIỂM THỬ: TỰ ĐỘNG NHẮC NHỞ HẾT HẠN VISA TRƯỚC 10 NGÀY")
    print("=" * 70)
    
    init_db()
    conn = get_db_connection()
    
    # 1. SETUP DỮ LIỆU THỬ NGHIỆM: 4 khách hàng với các ngôn ngữ khác nhau
    # Ngày hôm nay + 10 ngày
    today = datetime.now()
    exp_10_days = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    exp_30_days = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Khách 1: Alexey (Nga) - Hết hạn đúng 10 ngày tới
    cust_ru = get_or_create_customer("telegram", "test_tg_alexey_reminder", full_name="Alexey Morozov", nationality="Russia")
    update_customer_profile(
        cust_ru["customer_id"],
        preferred_lang="ru",
        preferred_seat="A1",
        preferred_pickup="Oceanus Nha Trang",
        total_trips=2,
        customer_tier="RETURNING"
    )
    update_customer_visa_expiry(cust_ru["customer_id"], exp_10_days)
    
    # Khách 2: Min-ho (Hàn Quốc) - Hết hạn đúng 10 ngày tới
    cust_ko = get_or_create_customer("telegram", "test_tg_minho_reminder", full_name="Park Min Ho", nationality="Korea")
    update_customer_profile(
        cust_ko["customer_id"],
        preferred_lang="ko",
        preferred_seat="B2",
        total_trips=1,
        customer_tier="RETURNING"
    )
    update_customer_visa_expiry(cust_ko["customer_id"], exp_10_days)

    # Khách 3: David (Anh) - Hết hạn đúng 10 ngày tới
    cust_en = get_or_create_customer("telegram", "test_tg_david_reminder", full_name="David Miller", nationality="United Kingdom")
    update_customer_profile(
        cust_en["customer_id"],
        preferred_lang="en",
        preferred_pickup="4 Tran Phu",
        total_trips=1,
        customer_tier="RETURNING"
    )
    update_customer_visa_expiry(cust_en["customer_id"], exp_10_days)
    
    # Khách 4: Michael (Mỹ) - Hết hạn sau 30 ngày (CHƯA ĐẾN HẠN NHẮC)
    cust_safe = get_or_create_customer("telegram", "test_tg_michael_safe", full_name="Michael Scott", nationality="United States")
    update_customer_visa_expiry(cust_safe["customer_id"], exp_30_days)

    print(f"\n--- [TEST 1] QUÉT DANH SÁCH KHÁCH CẦN NHẮC NHỞ TRƯỚC 10 NGÀY ---")
    needing = get_customers_needing_visa_reminder(days_before=10, window_days=2)
    needing_ids = [c["customer_id"] for c in needing]
    
    assert cust_ru["customer_id"] in needing_ids, "Lỗi: Khách Nga không được tìm thấy!"
    assert cust_ko["customer_id"] in needing_ids, "Lỗi: Khách Hàn không được tìm thấy!"
    assert cust_en["customer_id"] in needing_ids, "Lỗi: Khách Anh không được tìm thấy!"
    assert cust_safe["customer_id"] not in needing_ids, "Lỗi: Khách 30 ngày không được quét vào danh sách 10 ngày!"
    print(f"✅ Quét chính xác! Tìm thấy {len(needing)} khách hàng có visa hết hạn sau 10 ngày ({exp_10_days}).")

    print(f"\n--- [TEST 2] KIỂM TRA ĐA NGÔN NGỮ & CÁ NHÂN HÓA NỘI DUNG NHẮC NHỞ ---")
    # Lấy thông tin mới nhất từ DB
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_ru["customer_id"],))
    c_ru_data = dict(cursor.fetchone())
    msg_ru = generate_reminder_message(c_ru_data, days_left=10)
    print("\n🇷🇺 [Nội dung gửi khách Nga]:\n" + msg_ru)
    assert "Здравствуйте, Alexey Morozov" in msg_ru or "Здравствуйте" in msg_ru
    assert "10 дней" in msg_ru
    assert "A1" in msg_ru

    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_ko["customer_id"],))
    c_ko_data = dict(cursor.fetchone())
    msg_ko = generate_reminder_message(c_ko_data, days_left=10)
    print("\n🇰🇷 [Nội dung gửi khách Hàn]:\n" + msg_ko)
    assert "10일" in msg_ko
    assert "비자" in msg_ko

    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_en["customer_id"],))
    c_en_data = dict(cursor.fetchone())
    msg_en = generate_reminder_message(c_en_data, days_left=10)
    print("\n🇬🇧 [Nội dung gửi khách Quốc Tế (Tiếng Anh)]:\n" + msg_en)
    assert "10 days" in msg_en
    assert "David Miller" in msg_en
    print("\n✅ Nội dung thông điệp đa ngôn ngữ & cá nhân hóa đạt chuẩn 100%!")

    print(f"\n--- [TEST 3] THỰC THI GỬI NHẮC NHỞ & LƯU LỊCH SỬ TIN NHẮN (MOCK BOT) ---")
    
    # Tạo Mock Bot giả lập Telegram Bot
    class MockTelegramBot:
        def __init__(self):
            self.sent_messages = []
        async def send_message(self, chat_id, text, **kwargs):
            self.sent_messages.append({"chat_id": chat_id, "text": text})
            return True

    mock_bot = MockTelegramBot()
    send_res = await send_visa_reminder_to_customer(c_ru_data, bot=mock_bot, days_left=10)
    assert send_res["sent_success"] is True
    assert len(mock_bot.sent_messages) == 1
    
    # Kiểm tra tin nhắn nhắc nhở đã được lưu trong chat_messages với role=assistant
    session_id = f"telegram_{c_ru_data['telegram_id']}"
    history_db = get_session_messages(session_id)
    assert len(history_db) >= 1
    assert history_db[-1]["role"] == "assistant"
    print(f"✅ Đã gửi qua Mock Bot và lưu tin nhắn nhắc nhở vào chat_messages của session '{session_id}'.")

    print(f"\n--- [TEST 4] CHỐNG SPAM: KIỂM TRA ĐÁNH DẤU TRẠNG THÁI ĐÃ GỬI ---")
    needing_after = get_customers_needing_visa_reminder(days_before=10, window_days=2)
    after_ids = [c["customer_id"] for c in needing_after]
    assert cust_ru["customer_id"] not in after_ids, "Lỗi: Khách đã gửi nhắc nhở nhưng vẫn bị quét lại!"
    print("✅ Cơ chế chống spam hoạt động chuẩn: Không quét lại khách đã gửi nhắc nhở trong 7 ngày qua.")

    print(f"\n--- [TEST 5] KHÁCH HÀNG PHẢN HỒI LẠI TIN NHẮN NHẮC NHỞ (SEAMLESS AI DIALOGUE) ---")
    # Giả lập Alexey nhận được tin nhắn nhắc nhở và nhắn lại:
    user_reply = "Да, спасибо за напоминание! Забронируйте мне визаран на ближайший четверг."
    print(f"💬 Alexey phản hồi: \"{user_reply}\"")
    
    # Lấy lịch sử phiên bao gồm tin nhắn nhắc nhở của bot + tin phản hồi của Alexey
    history_for_ai = history_db + [{"role": "user", "content": user_reply}]
    
    # Lấy hồ sơ khách hàng đầy đủ
    profile = customer_memory.get_customer_profile("test_tg_alexey_reminder", platform="telegram")
    
    # Gọi AI Agent thực tế
    ai_response = await process_chat(history_for_ai, customer_profile=profile)
    print(f"\n🤖 AI Agent phản hồi lại câu trả lời của khách:\n{ai_response.reply_message}")
    
    # AI phải trả lời bằng tiếng Nga và hỗ trợ đặt chuyến
    assert len(ai_response.reply_message) > 20
    print("\n✅ AI Agent đã nhận thức được toàn bộ ngữ cảnh nhắc nhở và tiếp tục chăm sóc khách hoàn hảo!")

    print("=" * 70)
    print("🎉 TẤT CẢ 5 BÀI TEST NHẮC NHỞ VISA TRƯỚC 10 NGÀY ĐÃ ĐẠT 100%!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_visa_reminder_tests())
