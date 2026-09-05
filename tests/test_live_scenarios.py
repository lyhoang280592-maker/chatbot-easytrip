"""
test_live_scenarios.py - KIỂM THỬ TRỰC TIẾP TOÀN DIỆN CÁC KỊCH BẢN CHATBOT EASY TRIP & VISA
"""

import asyncio
import os
import sys
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from memory_store import memory_store
import customer_memory
from ai_agent import process_chat
from seat_map_generator import generate_seat_map

async def run_live_tests():
    print("=" * 80)
    print("🧪 BẮT ĐẦU CHẠY BỘ KIỂM THỬ TRỰC TIẾP 5 KỊCH BẢN VẬN HÀNH CỦA AI CHATBOT")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # KỊCH BẢN 1: KHÁCH HÀNG MỚI (MỸ / TIẾNG ANH) HỎI VISARUN
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 [KỊCH BẢN 1] KHÁCH MỚI (USA - Tiếng Anh) HỎI VISARUN TỪ NHA TRANG")
    print("-" * 70)
    
    session_1 = "test_tg_new_us_user"
    cust_new = customer_memory.get_or_create_customer("telegram", session_1, full_name="John Smith")
    
    msg_1 = "Hi! I am from the US, staying in Nha Trang. My visa expires on September 25th. Can I do a visa run?"
    print(f"👤 Khách hỏi: \"{msg_1}\"")
    
    res_1 = await process_chat([{"role": "user", "content": msg_1}], customer_profile=cust_new)
    print(f"\n🤖 Bot phản hồi:\n{res_1.reply_message}")
    
    # -------------------------------------------------------------------------
    # KỊCH BẢN 2: KHÁCH HÀNG CŨ (NGA / TIẾNG NGA) QUAY LẠI ĐẶT CHUYẾN MỚI
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 [KỊCH BẢN 2] KHÁCH CŨ (Nga - Alexey Morozov, ghế quen A1) QUAY LẠI")
    print("-" * 70)
    
    session_2 = "test_tg_returning_alexey"
    cust_old = customer_memory.get_or_create_customer("telegram", session_2, full_name="Alexey Morozov", nationality="Russia")
    customer_memory.update_customer_profile(
        cust_old["customer_id"],
        preferred_lang="ru",
        preferred_seat="A1",
        preferred_pickup="Oceanus Nha Trang",
        total_trips=2,
        customer_tier="RETURNING"
    )
    
    msg_2 = "Привет! Мне снова нужен визаран, виза заканчивается 28/09."
    print(f"👤 Khách cũ hỏi: \"{msg_2}\"")
    
    res_2 = await process_chat([{"role": "user", "content": msg_2}], customer_profile=cust_old)
    print(f"\n🤖 Bot phản hồi (Tiếng Nga & Cá nhân hóa):\n{res_2.reply_message}")

    # -------------------------------------------------------------------------
    # KỊCH BẢN 3: KHÁCH YÊU CẦU XEM SƠ ĐỒ GHẾ XE
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 [KỊCH BẢN 3] KHÁCH YÊU CẦU XEM SƠ ĐỒ GHẾ XE 21 CHỖ")
    print("-" * 70)
    
    out_map = os.path.join(ROOT_DIR, "static", "test_live_seatmap.jpg")
    booked = ["B1", "A3", "B5"]
    gen_res = generate_seat_map(booked, output_path=out_map)
    print(f"💺 Đã tạo ảnh sơ đồ xe (đã gạch chéo ghế bận {booked}): {'Thành công' if gen_res else 'Thất bại'}")
    
    msg_3 = "Cho mình xem sơ đồ ghế xe còn trống những chỗ nào nhé?"
    print(f"👤 Khách hỏi: \"{msg_3}\"")
    res_3 = await process_chat([{"role": "user", "content": msg_3}], customer_profile=cust_new)
    print(f"\n🤖 Bot phản hồi:\n{res_3.reply_message}")

    # -------------------------------------------------------------------------
    # KỊCH BẢN 4: HỎI BẢNG GIÁ E-VISA KHẨN & FAST TRACK SÂN BAY MỚI
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 [KỊCH BẢN 4] HỎI BẢNG GIÁ E-VISA KHẨN 1H, 2H, 4H & FAST TRACK")
    print("-" * 70)
    
    msg_4 = "Báo giá cho mình E-visa khẩn 1 giờ, 2 giờ, 4 giờ và Fast track đón sân bay Cam Ranh"
    print(f"👤 Khách hỏi: \"{msg_4}\"")
    res_4 = await process_chat([{"role": "user", "content": msg_4}], customer_profile=cust_new)
    print(f"\n🤖 Bot phản hồi:\n{res_4.reply_message}")

    # -------------------------------------------------------------------------
    # KỊCH BẢN 5: KHÁCH BÁO ĐÃ CHUYỂN KHOẢN THANH TOÁN
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 [KỊCH BẢN 5] KHÁCH BÁO ĐÃ CHUYỂN KHOẢN QUA VIETCOMBANK")
    print("-" * 70)
    
    msg_5 = "Mình đã chuyển khoản 4.000.000đ vào tài khoản Vietcombank của công ty rồi nhé."
    print(f"👤 Khách báo: \"{msg_5}\"")
    res_5 = await process_chat([{"role": "user", "content": msg_5}], customer_profile=cust_new)
    print(f"\n🤖 Bot phản hồi:\n{res_5.reply_message}")

    print("\n" + "=" * 80)
    print("🎉 TOÀN BỘ 5 KỊCH BẢN KIỂM THỬ ĐÃ THỰC THI THÀNH CÔNG 100%!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_live_tests())
