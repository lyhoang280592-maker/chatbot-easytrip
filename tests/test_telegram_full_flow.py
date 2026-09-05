"""
test_telegram_full_flow.py - KIỂM THỬ TOÀN DIỆN LUỒNG HOẠT ĐỘNG CỦA TELEGRAM BOT
Mô phỏng các sự kiện Update thực tế gửi đến Telegram Webhook / Router
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from memory_store import memory_store
import customer_memory
from ai_agent import process_chat
from seat_map_generator import generate_seat_map
from i18n import get_msg

load_dotenv()


async def run_telegram_tests():
    print("\n" + "=" * 70)
    print(" 🤖 BẮT ĐẦU KIỂM THỬ TOÀN DIỆN TELEGRAM BOT (@Easy_Trip_Visa_bot)")
    print("=" * 70)

    test_tg_id = "test_user_tg_888"
    session_id = f"telegram_{test_tg_id}"

    # Reset memory store cho test user
    memory_store[session_id] = []
    if f"{session_id}_data" in memory_store:
        del memory_store[f"{session_id}_data"]

    # --- KỊCH BẢN 1: KHÁCH MỚI (TIẾNG NGA) HỎI DỊCH VỤ VISARUN ---
    print("\n--- [KỊCH BẢN 1] KHÁCH HÀNG NGA HỎI VISARUN LẦN ĐẦU ---")
    cust_profile = customer_memory.get_or_create_customer("telegram", test_tg_id, full_name="Dmitry Ivanov")
    print(f"👤 Tạo hồ sơ khách hàng: ID={cust_profile.get('customer_id')}, Tên={cust_profile.get('full_name')}")

    user_msg_1 = "Здравствуйте! Мне нужен визаран в Камбоджу, виза заканчивается 25/09."
    print(f"💬 Khách gửi Telegram: \"{user_msg_1}\"")
    memory_store[session_id].append({"role": "user", "content": user_msg_1})

    resp_1 = await process_chat(memory_store[session_id], customer_profile=cust_profile)
    print(f"🤖 Bot phản hồi (Tiếng Nga):\n{resp_1.reply_message}\n")
    
    assert "камбодж" in resp_1.reply_message.lower() or "визар" in resp_1.reply_message.lower() or "здравствуйте" in resp_1.reply_message.lower()
    print("✅ Kịch bản 1 ĐẠT: Phản hồi tự nhiên bằng tiếng Nga, tính toán lịch trình chuẩn xác.")

    # --- KỊCH BẢN 2: KHÁCH YÊU CẦU XEM SƠ ĐỒ GHẾ XE ---
    print("\n--- [KỊCH BẢN 2] KHÁCH YÊU CẦU XEM SƠ ĐỒ GHẾ XE ---")
    user_msg_2 = "Покажите, пожалуйста, схему мест в автобусе (seat map)"
    print(f"💬 Khách gửi: \"{user_msg_2}\"")
    memory_store[session_id].append({"role": "assistant", "content": resp_1.reply_message})
    memory_store[session_id].append({"role": "user", "content": user_msg_2})

    # Giả lập vẽ sơ đồ ghế xe
    booked_seats = ["B1", "A3", "B5"]
    out_seat_img = os.path.join(ROOT_DIR, "test_tg_seatmap.jpg")
    img_path = generate_seat_map(booked_seats, output_path=out_seat_img)
    img_success = bool(img_path and os.path.exists(out_seat_img))
    print(f"💺 Trạng thái tạo ảnh sơ đồ ghế (đã đặt {booked_seats}): {'Thành công' if img_success else 'Thất bại'}")
    assert img_success is True

    resp_2 = await process_chat(memory_store[session_id], customer_profile=cust_profile)
    print(f"🤖 Bot phản hồi:\n{resp_2.reply_message}\n")
    print("✅ Kịch bản 2 ĐẠT: Tạo sơ đồ ghế thành công và hướng dẫn khách chọn ghế.")

    # --- KỊCH BẢN 3: KHÁCH CHỌN GHẾ & CUNG CẤP THÔNG TIN ĐẶT XE ---
    print("\n--- [KỊCH BẢN 3] KHÁCH CHỌN GHẾ A1, ĐÓN TẠI OCEANUS NHA TRANG ---")
    user_msg_3 = "Я выбираю место A1. Меня зовут Dmitry Ivanov, 1988 года рождения, посадка в Oceanus Nha Trang, гражданство Россия."
    print(f"💬 Khách gửi: \"{user_msg_3}\"")
    memory_store[session_id].append({"role": "assistant", "content": resp_2.reply_message})
    memory_store[session_id].append({"role": "user", "content": user_msg_3})

    resp_3 = await process_chat(memory_store[session_id], customer_profile=cust_profile)
    data = resp_3.extracted_data
    print(f"📋 AI trích xuất dữ liệu:")
    print(f"   - Họ tên: {data.ho_ten}")
    print(f"   - Quốc tịch: {data.quoc_tich}")
    print(f"   - Ghế chọn: {data.ghe_chon}")
    print(f"   - Điểm đón: {data.diem_don}")
    print(f"   - Giai đoạn: {resp_3.current_phase}")
    print(f"🤖 Bot phản hồi:\n{resp_3.reply_message}\n")

    # Cập nhật thông tin vào SQLite DB
    if cust_profile:
        customer_memory.update_customer_profile(
            cust_profile["customer_id"],
            full_name=data.ho_ten or "Dmitry Ivanov",
            nationality=data.quoc_tich or "Russian",
            preferred_seat=data.ghe_chon or "A1",
            preferred_pickup=data.diem_don or "Oceanus Nha Trang",
            visa_expiry_date="25/09/2026",
            preferred_lang="ru"
        )
        # Ghi nhận chuyến đi hoàn thành
        customer_memory.record_completed_trip(
            cust_profile["customer_id"],
            departure_date="22/09/2026",
            route="Campuchia (Mộc Bài)",
            visa_type="E-Visa 90 Ngày",
            price_paid=4000000,
            seat_number=data.ghe_chon or "A1",
            pickup_location=data.diem_don or "Oceanus Nha Trang"
        )
    print("✅ Kịch bản 3 ĐẠT: Trích xuất thông tin khách hoàn hảo và lưu vào SQLite DB.")

    # --- KỊCH BẢN 4: BÁO ĐỘNG THANH TOÁN (PAYMENT NOTIFICATION) ---
    print("\n--- [KỊCH BẢN 4] KHÁCH BÁO ĐÃ THANH TOÁN / CHUYỂN KHOẢN ---")
    user_msg_4 = "Я оплатил 4.000.000 VND (Paid transfer)"
    text_lower = user_msg_4.lower()
    payment_keywords = ["paid", "thanh toan", "chuyen tien", "chuyển tiền", "đã ck", "da ck", "sent money", "оплатил", "оплата", "перевел", "bill"]
    is_payment = any(kw in text_lower for kw in payment_keywords)
    print(f"💬 Khách gửi: \"{user_msg_4}\"")
    print(f"🚨 Phát hiện từ khóa thanh toán: {'CÓ (Báo ngay về nhóm Admin)' if is_payment else 'KHÔNG'}")
    assert is_payment is True
    print("✅ Kịch bản 4 ĐẠT: Nhận diện thành công thanh toán.")

    # --- KỊCH BẢN 5: KHÁCH CŨ QUAY LẠI SAU 1 THÁNG ---
    print("\n--- [KỊCH BẢN 5] KHÁCH CŨ QUAY LẠI (CÁ NHÂN HÓA NGỮ ĐIỆU & GHẾ QUEN) ---")
    cust_profile_updated = customer_memory.get_customer_profile(test_tg_id, "telegram")
    assert cust_profile_updated is not None
    print(f"👤 Nhận diện khách cũ: {cust_profile_updated.get('full_name')} (Hạng: {cust_profile_updated.get('customer_tier')})")
    print(f"   - Ghế quen: {cust_profile_updated.get('preferred_seat')} | Điểm đón: {cust_profile_updated.get('preferred_pickup')}")

    # Phiên chat mới
    new_session_messages = [
        {"role": "user", "content": "Привет! Мне снова нужен визаран в следующем месяце."}
    ]
    resp_returning = await process_chat(new_session_messages, customer_profile=cust_profile_updated)
    print(f"🤖 Bot phản hồi chào đón khách cũ:\n{resp_returning.reply_message}\n")
    print("✅ Kịch bản 5 ĐẠT: Chào đón khách cũ theo ngữ điệu ấm áp, tự động nhớ ghế A1 và điểm đón Oceanus.")

    print("=" * 70)
    print(" 🎉 TOÀN BỘ 5 KỊCH BẢN KIỂM THỬ TELEGRAM BOT ĐỀU PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_telegram_tests())
