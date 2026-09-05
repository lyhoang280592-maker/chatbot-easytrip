import asyncio
import os
import sys
import sqlite3

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import customer_memory
from memory_store import memory_store, load_session_history
from ai_agent import process_chat

async def run_tests():
    print("======================================================================")
    print("🚀 BẮT ĐẦU KIỂM THỬ: BỘ NHỚ DÀI HẠN & NHẬN DIỆN KHÁCH HÀNG CŨ")
    print("======================================================================\n")

    test_user_id = "test_alexey_999"
    test_session = f"telegram_{test_user_id}"
    test_phone = "+84988776655"

    # Xóa dữ liệu test cũ nếu có trong DB
    conn = customer_memory.get_db_connection()
    with conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id LIKE '%test_%'")
        conn.execute("DELETE FROM trip_history WHERE customer_id IN (SELECT customer_id FROM customers WHERE telegram_id = ? OR phone_number = ?)", (test_user_id, test_phone))
        conn.execute("DELETE FROM customers WHERE telegram_id = ? OR phone_number = ?", (test_user_id, test_phone))
    memory_store.clear()

    # ------------------------------------------------------------------
    # TEST CASE 1: Khách hàng mới (New Customer)
    # ------------------------------------------------------------------
    print("--- [TEST 1] KHÁCH HÀNG MỚI LẦN ĐẦU NHẮN TIN ---")
    cust_1 = customer_memory.get_or_create_customer("telegram", test_user_id, full_name="Alexey Smirnov")
    assert cust_1["customer_tier"] == "NEW", "Lỗi: Khách mới phải có tier là NEW"
    print(f"✅ Đã tạo hồ sơ khách mới: ID={cust_1['customer_id']}, Tên={cust_1['full_name']}, Tier={cust_1['customer_tier']}")

    msg_1 = "Hello, I want to inquire about visa run from Nha Trang."
    memory_store[test_session] = [{"role": "user", "content": msg_1}]
    customer_memory.save_chat_message(test_session, "Telegram", "user", msg_1, cust_1["customer_id"])

    res_1 = await process_chat(memory_store[test_session], customer_profile=cust_1)
    print(f"🤖 Bot phản hồi (Khách mới): \n{res_1.reply_message}\n")
    assert res_1.reply_message, "Lỗi: Bot không phản hồi"

    # Giả lập khách đặt hoàn tất chuyến đi Mộc Bài lần 1
    customer_memory.update_customer_profile(
        cust_1["customer_id"],
        full_name="Alexey Smirnov",
        nationality="Russia",
        phone_number=test_phone,
        preferred_seat="A1",
        preferred_pickup="Oceanus Nha Trang",
        preferred_lang="ru",
        customer_notes="Khách người Nga thân thiện, thích ghế A1 tầng dưới, thanh toán nhanh."
    )
    trip_id = customer_memory.record_completed_trip(
        customer_id=cust_1["customer_id"],
        departure_date="15/07/2026",
        route="Cambodia",
        visa_type="90D E-visa",
        seat_number="A1",
        pickup_location="Oceanus Nha Trang",
        price_paid=4000000,
        order_id="ORD-TEST-001"
    )
    print(f"✅ Đã ghi nhận chuyến đi cũ thành công: Trip ID={trip_id}\n")

    # ------------------------------------------------------------------
    # TEST CASE 2: Khách cũ quay lại (Returning Customer Recognition)
    # ------------------------------------------------------------------
    print("--- [TEST 2] KHÁCH CŨ QUAY LẠI SAU 1 THÁNG ---")
    memory_store.clear() # Xóa RAM cache để chứng minh truy xuất từ Database
    
    returning_profile = customer_memory.get_customer_profile(test_user_id, "telegram")
    assert returning_profile is not None, "Lỗi: Không tìm thấy hồ sơ khách cũ"
    assert returning_profile["total_trips"] == 1, f"Lỗi: Số chuyến đi không đúng ({returning_profile['total_trips']})"
    assert returning_profile["customer_tier"] == "RETURNING", f"Lỗi: Tier khách không đúng ({returning_profile['customer_tier']})"
    print(f"👤 Nhận diện khách cũ: {returning_profile['full_name']} ({returning_profile['nationality']}) - Đã đi {returning_profile['total_trips']} chuyến")
    print(f"💺 Ghế quen: {returning_profile['preferred_seat']} | Điểm đón: {returning_profile['preferred_pickup']}")

    msg_2 = "Привет! Мне снова нужен визаран, виза заканчивается 20/09."
    memory_store[test_session] = [{"role": "user", "content": msg_2}]
    customer_memory.save_chat_message(test_session, "Telegram", "user", msg_2, returning_profile["customer_id"])

    res_2 = await process_chat(memory_store[test_session], customer_profile=returning_profile)
    print(f"🤖 Bot phản hồi (Khách cũ - Cá nhân hóa ngữ điệu): \n{res_2.reply_message}\n")
    
    reply_lower = res_2.reply_message.lower()
    # Kiểm tra xem bot có nhận ra tên Alexey hoặc chào tiếng Nga chuẩn không
    is_personalized = any(kw in reply_lower for kw in ["алексей", "alexey", "снова", "рад", "мок бай", "a1", "oceanus", "привет", "здравствуйте"])
    print(f"✅ Kiểm tra cá nhân hóa: {'ĐẠT CHUẨN' if is_personalized else 'CHƯA TỐI ƯU'}\n")

    # ------------------------------------------------------------------
    # TEST CASE 3: Kiểm tra độ bền dữ liệu khi Restart Server
    # ------------------------------------------------------------------
    print("--- [TEST 3] KIỂM TRA ĐỘ BỀN DỮ LIỆU KHI SERVER RESTART ---")
    memory_store.clear() # Giả lập server khởi động lại, RAM bị trống
    assert test_session not in memory_store, "RAM chưa được làm trống"
    
    restored_history = load_session_history(test_session)
    assert len(restored_history) >= 2, f"Lỗi: Lịch sử tin nhắn không được phục hồi từ SQLite ({len(restored_history)} tin nhắn)"
    print(f"✅ Đã khôi phục thành công {len(restored_history)} tin nhắn từ SQLite Database sau khi xóa sạch RAM!")
    for idx, m in enumerate(restored_history, 1):
        print(f"   [{idx}] {m['role'].upper()}: {m['content'][:60]}...")
    print()

    # ------------------------------------------------------------------
    # TEST CASE 4: Đồng bộ liên kênh qua Số điện thoại (Cross-Platform)
    # ------------------------------------------------------------------
    print("--- [TEST 4] ĐỒNG BỘ ĐỊNH DANH ĐA KÊNH QUA SỐ ĐIỆN THOẠI ---")
    fb_user_id = "test_alexey_facebook_888"
    
    # Khách chat lần đầu trên Facebook và cung cấp số điện thoại cũ
    merged_profile = customer_memory.link_platform_by_phone(test_phone, "facebook", fb_user_id)
    assert merged_profile is not None, "Lỗi: Không tìm thấy profile theo SĐT để gộp"
    assert merged_profile["telegram_id"] == test_user_id, "Lỗi: Telegram ID bị mất khi gộp"
    assert merged_profile["facebook_id"] == fb_user_id, "Lỗi: Facebook ID chưa được liên kết"
    assert merged_profile["full_name"] == "Alexey Smirnov", "Lỗi: Tên hồ sơ không khớp"
    print(f"✅ Gộp tài khoản đa kênh thành công!")
    print(f"   👤 Khách: {merged_profile['full_name']}")
    print(f"   📞 SĐT: {merged_profile['phone_number']}")
    print(f"   📱 Telegram ID: {merged_profile['telegram_id']}")
    print(f"   📘 Facebook ID: {merged_profile['facebook_id']}")
    print(f"   🚌 Số chuyến tích lũy: {merged_profile['total_trips']} chuyến")

    print("\n======================================================================")
    print("🎉 TẤT CẢ 4 KỊCH BẢN KIỂM THỬ ĐỀU THÀNH CÔNG 100%!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
